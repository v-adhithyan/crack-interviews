from django.urls import path

from . import views
from . import interviews

urlpatterns = [
    path("health/", views.health, name="health"),
    path("auth/login/", views.auth_login, name="auth-login"),
    path("auth/logout/", views.auth_logout, name="auth-logout"),
    path("auth/me/", views.auth_me, name="auth-me"),
    path("scratchpad/", views.scratchpad_draft, name="scratchpad-draft"),
    path("scratchpad/run/", views.run_scratchpad, name="scratchpad-run"),
    path("interview-rooms/", interviews.create_interview_room, name="interview-room-create"),
    path("interview-rooms/<uuid:room_uuid>/", interviews.interview_room, name="interview-room-detail"),
    path("interview-rooms/<uuid:room_uuid>/close/", interviews.close_interview_room, name="interview-room-close"),
    path("interview-rooms/<uuid:room_uuid>/share/", interviews.share_interview_room, name="interview-room-share"),
    path("interview-rooms/<uuid:room_uuid>/run/", interviews.run_interview_room, name="interview-room-run"),
    path("questions/", views.question_list, name="question-list"),
    path("tracks/<slug:slug>/", views.track_detail, name="track-detail"),
    path("tracks/<slug:slug>/revision/", views.track_revision_list, name="track-revision-list"),
    path("questions/<slug:slug>/", views.question_detail, name="question-detail"),
    path("questions/<slug:slug>/reference-solution/", views.question_reference_solution, name="question-reference-solution"),
    path("questions/<slug:slug>/revision/", views.mark_question_for_revision, name="mark-question-revision"),
    path("questions/<slug:slug>/run/", views.run_code, name="run-code"),
    path("questions/<slug:slug>/custom-run/", views.run_custom_code, name="run-custom-code"),
    path("questions/<slug:slug>/submit/", views.submit_code, name="submit-code"),
    path("questions/<slug:slug>/submissions/", views.submission_list, name="submission-list"),
    path("revision/", views.revision_list, name="revision-list"),
    path("submissions/<int:pk>/", views.submission_detail, name="submission-detail"),
]
