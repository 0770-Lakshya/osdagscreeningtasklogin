from django.http import FileResponse
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .models import UserFile
from .serializers import FileSerializer


class FileListCreateView(generics.ListCreateAPIView):
    """list the logged-in user's files + upload a new one"""

    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserFile.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        uploaded = self.request.FILES.get("file")
        serializer.save(
            owner=self.request.user,
            size=uploaded.size if uploaded else 0,
        )


class FileDetailView(generics.RetrieveDestroyAPIView):
    """returns 404 if file doesn't exist, 403 if it belongs to another user"""

    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]
    queryset = UserFile.objects.all()

    def get_object(self):
        file_obj = generics.get_object_or_404(UserFile, pk=self.kwargs["pk"])
        if file_obj.owner_id != self.request.user.id:
            raise PermissionDenied("You do not have access to this file.")
        return file_obj


class FileDownloadView(APIView):
    """download the actual file bytes, only the owner can do this"""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            file_obj = UserFile.objects.get(pk=pk)
        except UserFile.DoesNotExist:
            raise NotFound("File not found.")
        if file_obj.owner_id != request.user.id:
            raise PermissionDenied("You do not have access to this file.")
        return FileResponse(
            file_obj.content.open("rb"),
            as_attachment=True,
            filename=file_obj.name,
        )
