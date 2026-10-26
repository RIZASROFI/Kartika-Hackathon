from django.contrib import admin
from django.urls import include, path, re_path

from intel.views import health_view, spa_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health_view, name="health"),
    path("api/v1/", include("intel.urls")),
    re_path(r"^(?P<path>.*)$", spa_view, name="spa"),
]
