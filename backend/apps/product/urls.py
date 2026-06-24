from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("app/", views.dashboard, name="product_dashboard"),
    path("app/analysis/", views.analysis_history, name="analysis_history"),
    path("app/analysis/<int:analysis_id>/", views.analysis_detail, name="analysis_detail"),
    path("app/analysis/<int:analysis_id>/status/", views.analysis_status, name="analysis_status"),
    path("app/quick-refresh/", views.quick_refresh, name="quick_refresh"),
    path("user-content/resume/<uuid:resume_uuid>/", views.resume_content, name="resume_content"),
    path("login/", views.ProductLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("signup/<uuid:token>/", views.early_access_signup, name="early_access_signup"),
]
