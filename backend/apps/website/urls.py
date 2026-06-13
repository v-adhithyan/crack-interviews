from django.urls import path

from . import views

urlpatterns = [
    path('blog/', views.blog_index, name='blog_index'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),
    path('refund-policy/', views.refund_policy, name='refund_policy'),
    path('pricing/', views.pricing_page, name='pricing_page'),
    path('', views.home_page, name='home_page'),
]
