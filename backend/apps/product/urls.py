from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("app/", views.dashboard, name="product_dashboard"),
    path("login/", views.ProductLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("signup/<uuid:token>/", views.early_access_signup, name="early_access_signup"),
]
