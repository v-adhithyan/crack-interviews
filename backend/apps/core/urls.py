from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("auth/login/", views.auth_login, name="auth-login"),
    path("auth/logout/", views.auth_logout, name="auth-logout"),
    path("auth/me/", views.auth_me, name="auth-me"),
    path("questions/", views.question_list, name="question-list"),
    path("questions/<slug:slug>/", views.question_detail, name="question-detail"),
    path("questions/<slug:slug>/reference-solution/", views.question_reference_solution, name="question-reference-solution"),
    path("questions/<slug:slug>/run/", views.run_code, name="run-code"),
    path("questions/<slug:slug>/submit/", views.submit_code, name="submit-code"),
    path("questions/<slug:slug>/submissions/", views.submission_list, name="submission-list"),
    path("submissions/<int:pk>/", views.submission_detail, name="submission-detail"),
]
