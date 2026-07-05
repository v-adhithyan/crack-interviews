from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
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
    path("app/mock-interview/<uuid:session_uuid>/continue-free-style/", views.mock_interview_continue_free_style, name="mock_interview_continue_free_style"),
    path("app/mock-interview/<uuid:session_uuid>/token/", views.mock_interview_token, name="mock_interview_token"),
    path("app/mock-interview/<uuid:session_uuid>/turns/", views.mock_interview_turns, name="mock_interview_turns"),
    path("app/mock-interview/<uuid:session_uuid>/finish/", views.mock_interview_finish, name="mock_interview_finish"),
    path("app/mock-interview/<uuid:session_uuid>/feedback/", views.mock_interview_feedback, name="mock_interview_feedback"),
    path("app/mock-interview/share/<uuid:share_uuid>/", views.mock_interview_public_share, name="mock_interview_public_share"),
    path("user-content/resume/<uuid:resume_uuid>/", views.resume_content, name="resume_content"),
    path("login/", views.ProductLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("signup/<uuid:token>/", views.early_access_signup, name="early_access_signup"),
]
