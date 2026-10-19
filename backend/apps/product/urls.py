from django.contrib.auth.views import LogoutView
from django.urls import path

from . import resume_edit_views
from . import resume_pdf_views
from . import followup_views
from . import views
from . import resume_builder_views as builder

urlpatterns = [
    path("app/analysis/<uuid:analysis_uuid>/followups/", followup_views.create, name="analysis_followup_create"),
    path("app/followups/<uuid:job_uuid>/", followup_views.detail, name="analysis_followup_detail"),
    path("app/followups/<uuid:job_uuid>/status/", followup_views.status, name="analysis_followup_status"),
    path("app/resume-pdf/<uuid:job_uuid>/", resume_pdf_views.detail, name="resume_pdf_detail"),
    path("app/resume-pdf/<uuid:job_uuid>/status/", resume_pdf_views.status, name="resume_pdf_status"),
    path("app/resume-pdf/<uuid:job_uuid>/file/", resume_pdf_views.file, name="resume_pdf_file"),
    path("app/analysis/<uuid:analysis_uuid>/resume-edits/", resume_edit_views.review, name="resume_edits_review"),
    path("app/analysis/<uuid:analysis_uuid>/resume-edits/apply/", resume_edit_views.apply, name="resume_edits_apply"),
    path("app/resume-builder/", builder.draft_list, name="resume_builder_list"),
    path("app/resume-builder/create/", builder.draft_create, name="resume_builder_create"),
    path("app/resume-builder/<uuid:draft_uuid>/", builder.draft_edit, name="resume_builder_edit"),
    path("app/resume-builder/<uuid:draft_uuid>/save/", builder.draft_save, name="resume_builder_save"),
    path("app/resume-builder/<uuid:draft_uuid>/preview/", builder.draft_preview, name="resume_builder_preview"),
    path("app/resume-builder/<uuid:draft_uuid>/export/", resume_pdf_views.export, name="resume_builder_export"),
    path("app/resume-builder/<uuid:draft_uuid>/use/", builder.draft_use, name="resume_builder_use"),
    path("app/resume-builder/<uuid:draft_uuid>/delete/", builder.draft_delete, name="resume_builder_delete"),
    path("app/resume-builder/<uuid:draft_uuid>/clone/", builder.draft_clone, name="resume_builder_clone"),

    path("app/", views.dashboard, name="product_dashboard"),
    path("app/code/", views.code_platform_redirect, name="code_platform_redirect"),
    path("app/resume/", views.current_resume_content, name="current_resume_content"),
    path("app/analysis/", views.analysis_history, name="analysis_history"),
    path("app/analysis/<uuid:analysis_uuid>/", views.analysis_detail, name="analysis_detail"),
    path("app/analysis/<uuid:analysis_uuid>/status/", views.analysis_status, name="analysis_status"),
    path("app/mock-interview/", views.mock_interview_start, name="mock_interview_start"),
    path("app/mock-interview/start/", views.mock_interview_create, name="mock_interview_create"),
    path("app/mock-interview/history/", views.mock_interview_history, name="mock_interview_history"),
    path("app/mock-interview/<uuid:session_uuid>/", views.mock_interview_room, name="mock_interview_room"),
    path("app/mock-interview/<uuid:session_uuid>/continue-free-style/", views.mock_interview_continue_free_style,
         name="mock_interview_continue_free_style"),
    path("app/mock-interview/<uuid:session_uuid>/token/", views.mock_interview_token, name="mock_interview_token"),
    path("app/mock-interview/<uuid:session_uuid>/turns/", views.mock_interview_turns, name="mock_interview_turns"),
    path("app/mock-interview/<uuid:session_uuid>/finish/", views.mock_interview_finish, name="mock_interview_finish"),
    path("app/mock-interview/<uuid:session_uuid>/feedback/", views.mock_interview_feedback,
         name="mock_interview_feedback"),
    path("user-content/resume/<uuid:resume_uuid>/", views.resume_content, name="resume_content"),
    path("login/", views.ProductLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("signup/<uuid:token>/", views.early_access_signup, name="early_access_signup"),
]
