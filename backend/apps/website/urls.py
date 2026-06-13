from django.urls import path

from . import views

urlpatterns = [
    path('blog/', views.blog_index, name='blog_index'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('', views.home_page, name='home_page'),
]
