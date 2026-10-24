from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .decorators import product_access_required
from .models import ResumeDraft, ResumePrunePlan
from .resume_builder import render_resume
from .resume_pruner import snapshot, suggest, candidate_list, consolidate, fingerprint


def lock_user(user):
    get_user_model().objects.select_for_update().get(pk=user.pk)


def get_plan(request, plan_uuid, lock=False):
    query = ResumePrunePlan.objects.select_for_update() if lock else ResumePrunePlan.objects
    return get_object_or_404(query, uuid=plan_uuid, user=request.user, expires_at__gt=timezone.now())


def review_error(exc, status=400):
    return HttpResponse(' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc), status=status, content_type='text/plain')


@never_cache
@product_access_required
@require_POST
def mark_base(request, draft_uuid):
    with transaction.atomic():
        lock_user(request.user)
        draft = get_object_or_404(ResumeDraft.objects.select_for_update(), uuid=draft_uuid, user=request.user)
        if request.POST.get('revision') != str(draft.revision):
            return review_error('This resume changed. Reload before marking it.', 409)
        if request.POST.get('is_base') not in ('0', '1'):
            return review_error('Choose whether this is a base resume.')
        wanted = request.POST['is_base'] == '1'
        if wanted and not draft.is_base and ResumeDraft.objects.filter(user=request.user, is_base=True).count() >= 5:
            return review_error('You can protect at most five base resumes. Unmark one first.', 409)
        if draft.is_base != wanted:
            draft.is_base = wanted
            draft.revision += 1
            draft.save(update_fields=['is_base', 'revision', 'updated_at'])
    return redirect('resume_pruner')


@never_cache
@product_access_required
@require_http_methods(['GET', 'POST'])
def start(request):
    if request.method == 'POST':
        with transaction.atomic():
            lock_user(request.user)
            drafts = list(ResumeDraft.objects.select_for_update().filter(user=request.user))
            if not 1 <= sum(d.is_base for d in drafts) <= 5 or not any(not d.is_base for d in drafts):
                messages.error(request, 'Mark one to five bases and keep at least one non-base draft to review.')
                return redirect('resume_pruner')
            if ResumePrunePlan.objects.filter(user=request.user, expires_at__gt=timezone.now()).count() >= 3:
                messages.error(request, 'You already have three active prune reviews. Finish or discard one first.')
                return redirect('resume_pruner')
            try:
                snapshots = {str(d.uuid): snapshot(d) for d in drafts}
            except ValidationError as exc:
                return review_error(exc)
            plan = ResumePrunePlan.objects.create(user=request.user, snapshots=snapshots, expires_at=timezone.now()+timedelta(hours=24))
        return redirect('resume_prune_review', plan_uuid=plan.uuid)
    return render(request, 'product/resume_pruner/start.html', {'drafts': ResumeDraft.objects.filter(user=request.user),
        'plans': ResumePrunePlan.objects.filter(user=request.user, expires_at__gt=timezone.now()).order_by('-created_at'),
        'active_nav': 'resume_pruner'})


def assert_current(plan, user):
    current = {str(d.uuid): d for d in ResumeDraft.objects.select_for_update().filter(user=user, uuid__in=plan.snapshots)}
    if len(current) != len(plan.snapshots) or any(fingerprint(current[key]) != value['fingerprint'] for key, value in plan.snapshots.items()):
        raise ValidationError('A reviewed resume was edited, deleted, or marked/unmarked as a base. Nothing was changed. Start a new prune review.')


@never_cache
@product_access_required
@require_http_methods(['GET', 'POST'])
def review(request, plan_uuid):
    failure = ''
    if request.method == 'POST':
        with transaction.atomic():
            lock_user(request.user)
            plan = get_plan(request, plan_uuid, lock=True)
            if request.POST.get('revision') != str(plan.revision):
                return review_error('This review changed in another tab. Reload it.', 409)
            if plan.stage not in ('assign', 'review', 'preview'):
                return review_error('This prune review has already finished.', 409)
            try:
                assert_current(plan, request.user)
            except ValidationError as exc:
                return review_error(exc, 409)
            try:
                action = request.POST.get('action')
                if action == 'back':
                    plan.stage = 'assign'
                    plan.outputs = []; plan.delete_ids = []; plan.candidates = []
                elif plan.stage == 'assign' and action == 'assign':
                    bases = {key for key, value in plan.snapshots.items() if value['is_base']}
                    assignments = {key: request.POST.get('group_' + key, '') for key, value in plan.snapshots.items() if not value['is_base']}
                    if not set(assignments.values()) <= bases | {''} or not any(assignments.values()):
                        raise ValidationError('Assign at least one draft to a valid base. Leave uncertain drafts unassigned.')
                    plan.assignments = assignments
                    plan.candidates = candidate_list(plan.snapshots, assignments)
                    plan.stage = 'review'
                elif plan.stage == 'review' and action == 'preview':
                    delete_ids = request.POST.getlist('delete')
                    if len(set(delete_ids)) != len(delete_ids) or not set(delete_ids) <= {key for key, value in plan.assignments.items() if value}:
                        raise ValidationError('Only assigned non-base resumes may be selected for deletion.')
                    plan.outputs = consolidate(plan, request.POST.getlist('suggestion'))
                    if ResumeDraft.objects.filter(user=request.user).count() - len(delete_ids) + len(plan.outputs) > 20:
                        raise ValidationError('This result would exceed 20 resumes. Select enough reviewed source drafts for deletion or consolidate fewer groups.')
                    plan.delete_ids = delete_ids
                    plan.stage = 'preview'
                else:
                    raise ValidationError('Invalid review action.')
                plan.revision += 1
                plan.save()
                return redirect('resume_prune_review', plan_uuid=plan.uuid)
            except ValidationError as exc:
                failure = ' '.join(exc.messages)
    else:
        plan = get_plan(request, plan_uuid)
    bases = [{'id': key, **value} for key, value in plan.snapshots.items() if value['is_base']]
    suggestions = suggest(plan.snapshots)
    sources = [{'id': key, **value, 'suggestion': suggestions[key], 'selected': plan.assignments.get(key, suggestions[key]['base']), 'delete_selected': key in request.POST.getlist('delete')} for key, value in plan.snapshots.items() if not value['is_base']]
    candidates = [{**item, 'selected': item['id'] in request.POST.getlist('suggestion'), 'base_title': plan.snapshots[item['base']]['title'],
                   'source_titles': ', '.join(plan.snapshots[key]['title'] for key in item['sources'])} for item in plan.candidates]
    previews = [{**item, 'html': render_resume(item['content']).replace('</head>', '<style>@media screen and (max-width:800px){body{width:100%;min-height:0;margin:0;padding:20px;box-shadow:none}}</style></head>')} for item in plan.outputs] if plan.stage == 'preview' else []
    return render(request, 'product/resume_pruner/review.html', {'plan': plan, 'bases': bases, 'sources': sources,
        'candidates': candidates, 'previews': previews, 'deletions': [plan.snapshots[key]['title'] for key in plan.delete_ids],
        'failure': failure, 'active_nav': 'resume_pruner'}, status=400 if failure else 200)


@never_cache
@product_access_required
@require_GET
def backup(request, plan_uuid):
    plan = get_plan(request, plan_uuid)
    response = JsonResponse({'format': 'hackerleap-resume-prune-backup-v1', 'created_at': plan.created_at.isoformat(),
        'resumes': [{'uuid': key, **{k: v for k, v in value.items() if k != 'fingerprint'}} for key, value in plan.snapshots.items()]}, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    response['Content-Disposition'] = 'attachment; filename="resume-pruner-backup.json"'
    return response


@never_cache
@product_access_required
@require_POST
def apply(request, plan_uuid):
    with transaction.atomic():
        lock_user(request.user)
        plan = get_plan(request, plan_uuid, lock=True)
        if plan.stage == 'complete':
            return redirect('resume_prune_review', plan_uuid=plan.uuid)
        if plan.stage != 'preview' or request.POST.get('revision') != str(plan.revision):
            return review_error('Review the latest consolidated previews first.', 409)
        if request.POST.get('confirm') != 'yes':
            return review_error('Confirm the listed creations and permanent deletions first.')
        try:
            assert_current(plan, request.user)
        except ValidationError as exc:
            return review_error(exc, 409)
        deletion = ResumeDraft.objects.filter(user=request.user, uuid__in=plan.delete_ids, is_base=False)
        final_count = ResumeDraft.objects.filter(user=request.user).count() - deletion.count() + len(plan.outputs)
        if final_count > 20:
            return review_error('New drafts were added and the result would exceed 20 resumes. Start a new review.', 409)
        # Delete and create in one transaction; any creation error restores every source.
        deletion.delete()
        results = [ResumeDraft.objects.create(user=request.user, title=item['title'], content=item['content'],
                    template_version=item['template_version']) for item in plan.outputs]
        plan.result_ids = [str(d.uuid) for d in results]
        plan.stage = 'complete'; plan.revision += 1
        plan.save(update_fields=['result_ids', 'stage', 'revision'])
    messages.success(request, 'Consolidated resumes created. Your protected bases are unchanged.')
    return redirect('resume_prune_review', plan_uuid=plan.uuid)


@never_cache
@product_access_required
@require_POST
def discard(request, plan_uuid):
    with transaction.atomic():
        lock_user(request.user)
        get_plan(request, plan_uuid, lock=True).delete()
    return redirect('resume_pruner')
