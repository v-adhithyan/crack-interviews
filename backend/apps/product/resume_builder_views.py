import json
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages

from .decorators import product_access_required
from .models import Resume, ResumeDraft
from .pdf import extract_pdf_text
from .resume_builder import MAX_BODY, blank_content, fields, render_pdf, render_resume, validate_content


def draft_for(request, draft_uuid):
    return get_object_or_404(ResumeDraft, uuid=draft_uuid, user=request.user)


def payload(request):
    raw = request.read(MAX_BODY + 1)
    if request.content_type != 'application/json' or len(raw) > MAX_BODY:
        raise ValidationError('Send a JSON request smaller than 100 KB.')
    def unique(items):
        data = {}
        for key, value in items:
            if key in data:
                raise ValueError('Duplicate key')
            data[key] = value
        return data
    try:
        data = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(data, dict):
            raise ValueError('Object required')
        return data
    except (ValueError, RecursionError):
        raise ValidationError('Invalid JSON request.')


def error(exc):
    return JsonResponse({'detail': ' '.join(exc.messages)}, status=400)


@never_cache
@product_access_required
@require_GET
def draft_list(request):
    return render(request, 'product/resume_builder/list.html', {'drafts': ResumeDraft.objects.filter(user=request.user), 'active_nav': 'resume_builder'})


@product_access_required
@require_POST
def draft_create(request):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        if ResumeDraft.objects.filter(user=request.user).count() >= 20:
            messages.error(request, 'You can keep up to 20 resume drafts. Delete an unused draft first.')
            return redirect('resume_builder_list')
        draft = ResumeDraft.objects.create(user=request.user, content=blank_content())
    return redirect('resume_builder_edit', draft_uuid=draft.uuid)


@never_cache
@product_access_required
@require_GET
def draft_edit(request, draft_uuid):
    draft = draft_for(request, draft_uuid)
    return render(request, 'product/resume_builder/editor.html', {'draft': draft, 'initial': {'title': draft.title, 'revision': draft.revision, 'content': draft.content}, 'active_nav': 'resume_builder'})


@never_cache
@product_access_required
@require_POST
def draft_save(request, draft_uuid):
    draft = draft_for(request, draft_uuid)
    try:
        data = payload(request)
        if set(data) != {'title', 'content', 'revision'} or type(data['revision']) is not int or data['revision'] < 1:
            raise ValidationError('A title, content and positive integer revision are required.')
        title = fields({'title': data['title']}, {'title': 120})['title'] or 'Untitled resume'
        content = validate_content(data['content'])
    except ValidationError as exc:
        return error(exc)
    # Atomic compare-and-swap: never read/check/save in separate database operations.
    changed = ResumeDraft.objects.filter(pk=draft.pk, user=request.user, revision=data['revision']).update(title=title, content=content, revision=F('revision') + 1, updated_at=timezone.now())
    if not changed:
        return JsonResponse({'detail': 'This resume changed in another tab. Your edits are still here. Download a recovery copy before loading the latest draft.'}, status=409)
    return JsonResponse({'revision': data['revision'] + 1})


@never_cache
@product_access_required
@require_POST
def draft_preview(request, draft_uuid):
    draft_for(request, draft_uuid)
    try:
        data = payload(request)
        if set(data) != {'content'}:
            raise ValidationError('Only content is accepted for preview.')
        html = render_resume(data['content'])
    except ValidationError as exc:
        return error(exc)
    return JsonResponse({'html': html})


@never_cache
@product_access_required
@require_POST
def draft_export(request, draft_uuid):
    draft = draft_for(request, draft_uuid)
    # Exports are tied to a saved version, so another tab cannot change what is exported unnoticed.
    if request.POST.get('revision') != str(draft.revision):
        return HttpResponse('Draft changed. Return to the editor and save or load the latest version.', status=409)
    key = f'resume-export:{request.user.pk}'
    if not cache.add(key, True, timeout=10):
        return HttpResponse('Please wait a few seconds before exporting again.', status=429)
    try:
        pdf = render_pdf(draft.content)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=400, content_type='text/plain')
    except RuntimeError as exc:
        return HttpResponse(str(exc), status=503, content_type='text/plain')
    response = HttpResponse(pdf, content_type='application/pdf')
    disposition = 'attachment' if request.POST.get('download') == '1' else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="resume.pdf"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@product_access_required
@require_POST
def draft_use(request, draft_uuid):
    draft = draft_for(request, draft_uuid)
    if request.POST.get('revision') != str(draft.revision):
        return HttpResponse('Draft changed. Return to the editor and load the latest version.', status=409)
    if not cache.add(f'resume-export:{request.user.pk}', True, timeout=10):
        return HttpResponse('Please wait a few seconds before generating another PDF.', status=429)
    try:
        pdf = render_pdf(draft.content)
        parsed = extract_pdf_text(BytesIO(pdf))
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=400, content_type='text/plain')
    except RuntimeError as exc:
        return HttpResponse(str(exc), status=503, content_type='text/plain')
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        latest = ResumeDraft.objects.select_for_update().filter(pk=draft.pk, revision=draft.revision).exists()
        if not latest:
            return HttpResponse('Draft changed during export. Please try again.', status=409)
        resume, _ = Resume.objects.get_or_create(user=request.user, defaults={'original_filename': 'resume.pdf', 'content_type': 'application/pdf', 'size': len(pdf)})
        old_name = resume.file.name
        storage = resume.file.storage
        resume.original_filename = 'resume.pdf'
        resume.content_type = 'application/pdf'
        resume.size = len(pdf)
        resume.builder_snapshot = {"draft_uuid": str(draft.uuid), "revision": draft.revision, "template_version": draft.template_version, "title": draft.title, "content": draft.content}
        resume.parsed_text = parsed
        resume.file.save('resume.pdf', ContentFile(pdf), save=False)
        resume.save()
        if old_name and old_name != resume.file.name:
            transaction.on_commit(lambda: storage.delete(old_name))
    messages.success(request, 'This saved resume is now selected for analysis.')
    return redirect('product_dashboard')


@product_access_required
@require_POST
def draft_delete(request, draft_uuid):
    draft = draft_for(request, draft_uuid)
    deleted, _ = ResumeDraft.objects.filter(pk=draft.pk, revision=request.POST.get('revision', '')).delete() if request.POST.get('revision', '').isdigit() else (0, {})
    if not deleted:
        return HttpResponse('Draft changed. Reload the list before deleting.', status=409)
    return redirect('resume_builder_list')
