from django.urls import path

from . import views

urlpatterns = [
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('blog/', views.blog_index, name='blog_index'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),
    path('refund-policy/', views.refund_policy, name='refund_policy'),
    path('pricing/', views.pricing_page, name='pricing_page'),
    path('about/', views.website_page, {"slug": "about"}, name='about_page'),
    path('faq/', views.website_page, {"slug": "faq"}, name='faq_page'),
    path('', views.home_page, name='home_page'),
]
