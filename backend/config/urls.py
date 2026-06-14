from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("", include("apps.product.urls")),
    path("", include("apps.website.urls")),
]

handler404 = "apps.website.views.page_not_found"
handler500 = "apps.website.views.server_error"

admin.site.site_header = "HackerLeap"
admin.site.site_title = "HackerLeap Admin"
admin.site.index_title = "Welcome to HackerLeap Admin"
