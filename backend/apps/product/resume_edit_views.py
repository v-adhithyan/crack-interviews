import hashlib
import copy
import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .decorators import product_access_required
from .models import ResumeAnalysis, ResumeDraft, ResumeEditApplication
from .resume_edits import apply_edits, plan_token, review_edits, recommended_skills, add_recommended_skills


def eligible(analysis):
    return (analysis.status == ResumeAnalysis.Status.RESULT_ADDED
            and analysis.result_data.get('status') == 'success'
            and analysis.builder_snapshot.get('template_version') == 1)


@never_cache
@product_access_required
@require_GET
def review(request, analysis_uuid):
    analysis = get_object_or_404(ResumeAnalysis, uuid=analysis_uuid, user=request.user)
    if not eligible(analysis):
        return HttpResponse('Select a saved builder resume and run a new analysis before regenerating.', status=400)
    try:
        rows = review_edits(analysis)
        skills = recommended_skills(analysis)
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages), status=400, content_type='text/plain')
    return render(request, 'product/resume_builder/review_edits.html', {
        'analysis': analysis, 'rows': rows, 'plan_token': plan_token(analysis),
        'skills': skills, 'skill_groups': analysis.builder_snapshot['content']['skills'],
        'has_valid': any(not row['problem'] for row in rows) or any(not row['existing'] for row in skills), 'active_nav': 'resume_builder',
    })


@never_cache
@product_access_required
@require_POST
def apply(request, analysis_uuid):
    with transaction.atomic():
        # Serialize with draft creation and lock the result through validation/creation.
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        analysis = get_object_or_404(ResumeAnalysis.objects.select_for_update(), uuid=analysis_uuid, user=request.user)
        if not eligible(analysis):
            return HttpResponse('This analysis cannot regenerate a builder resume.', status=400)
        token = plan_token(analysis)
        if request.POST.get('plan_token') != token:
            return HttpResponse('The analysis changed. Reload the review page before applying edits.', status=409)
        selected = request.POST.getlist('targets')
        selected_skills = request.POST.getlist('skills')
        group = request.POST.get('skill_group', '') if selected_skills else ''
        try:
            content = apply_edits(analysis, selected) if selected or not selected_skills else copy.deepcopy(analysis.builder_snapshot['content'])
            content = add_recommended_skills(analysis, content, selected_skills, group, request.POST.get('confirm_skills') == '1')
        except ValidationError as exc:
            return HttpResponse(' '.join(exc.messages), status=400, content_type='text/plain')
        key_input = token + ':' + ','.join(sorted(selected))
        if selected_skills:
            key_input += ':' + json.dumps({'skills': sorted(selected_skills), 'group': group}, sort_keys=True)
        key = hashlib.sha256(key_input.encode()).hexdigest()
        previous = ResumeEditApplication.objects.filter(analysis=analysis, key=key).first()
        if previous:
            if previous.draft_id:
                return redirect('resume_builder_edit', draft_uuid=previous.draft.uuid)
            return HttpResponse('The previously generated draft was deleted. Run a new analysis to regenerate it.', status=409)
        if ResumeDraft.objects.filter(user=request.user).count() >= 20:
            return HttpResponse('You can keep up to 20 drafts. Delete an unused draft first.', status=400)
        snapshot = analysis.builder_snapshot
        draft = ResumeDraft.objects.create(user=request.user, title=(snapshot['title'][:100] + ' — improved'), content=content, template_version=snapshot['template_version'])
        ResumeEditApplication.objects.create(analysis=analysis, key=key, selected_targets=sorted(selected) + [f'skill:{group}:{item}' for item in sorted(selected_skills)], draft=draft)
    messages.success(request, 'Improved draft created from the analyzed version. Review it before downloading or selecting it for analysis.')
    return redirect('resume_builder_edit', draft_uuid=draft.uuid)
