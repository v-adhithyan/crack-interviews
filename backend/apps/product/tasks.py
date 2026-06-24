from django.db import transaction
from django.utils import timezone

from .models import ResumeAnalysis
from .services import run_resume_match_analysis


def run_resume_analysis(analysis_id):
    with transaction.atomic():
        analysis = ResumeAnalysis.objects.select_for_update().get(id=analysis_id)
        if analysis.status == ResumeAnalysis.Status.RESULT_ADDED:
            return
        analysis.status = ResumeAnalysis.Status.PROCESSING
        analysis.error_message = ""
        analysis.started_at = analysis.started_at or timezone.now()
        analysis.save(update_fields=("status", "error_message", "started_at", "updated_at"))

    try:
        analysis = ResumeAnalysis.objects.get(id=analysis_id)
        result = run_resume_match_analysis(
            job_description=analysis.job_description,
            resume_text=analysis.resume_text,
        )
    except Exception as exc:
        ResumeAnalysis.objects.filter(id=analysis_id).update(
            status=ResumeAnalysis.Status.FAILED,
            error_message=str(exc) or "Unable to complete AI analysis right now. Please try again later.",
            completed_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return

    ResumeAnalysis.objects.filter(id=analysis_id).update(
        generated_prompt=result.generated_prompt,
        ai_response_json=result.ai_response_json,
        ai_provider=result.provider,
        status=ResumeAnalysis.Status.RESULT_ADDED if result.is_complete else ResumeAnalysis.Status.PROMPT_READY,
        error_message="",
        completed_at=timezone.now(),
        updated_at=timezone.now(),
    )
