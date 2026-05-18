from django.contrib import admin
from django.urls import include, path

from corpus.views import api_root

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", api_root),
    path("api/", include("corpus.urls")),
]
