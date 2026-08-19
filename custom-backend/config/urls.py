from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # The provided index.html test client and mock-api.js define these exact
    # routes at the API root (no /api prefix, no trailing slashes):
    #   /register /login /refresh /logout /me
    #   /files /files/<id> /files/<id>/download
    path("", include("users.urls")),
    path("", include("files.urls")),
]
