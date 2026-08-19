from django.urls import path

from . import views

urlpatterns = [
    path("files", views.FileListCreateView.as_view(), name="file-list"),
    path("files/<int:pk>", views.FileDetailView.as_view(), name="file-detail"),
    path("files/<int:pk>/download", views.FileDownloadView.as_view(), name="file-download"),
]
