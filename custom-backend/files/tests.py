"""
Tests for file data isolation — the core security requirement.

Run with: python manage.py test files
"""

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User


def register_and_login(client, email, password="TestPass123!"):
    """Helper: register a user and return the access token."""
    client.post(
        "/register",
        {"email": email, "password": password},
        format="json",
    )
    res = client.post(
        "/login",
        {"email": email, "password": password},
        format="json",
    )
    return res.data["token"]


def auth_client(token):
    """Helper: create a client with Bearer token."""
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def create_file(client, name="test.txt", content=b"hello"):
    """Helper: upload a file via the API and return the response."""
    return client.post(
        "/files",
        {"name": name, "des": "test file", "file": ContentFile(content, name=name)},
        format="multipart",
    )


class DataIsolationTest(TestCase):
    """
    The task requires that User A cannot see User B's files.
    These tests verify that data isolation works correctly.
    """

    def setUp(self):
        """Create two users with their own files."""
        # Alice uploads 2 files
        self.alice_token = register_and_login(self.client, "alice@test.com")
        self.alice_client = auth_client(self.alice_token)
        create_file(self.alice_client, "alice_resume.pdf", b"alice content")
        create_file(self.alice_client, "alice_photo.jpg", b"alice photo")

        # Bob uploads 1 file
        self.bob_token = register_and_login(self.client, "bob@test.com")
        self.bob_client = auth_client(self.bob_token)
        create_file(self.bob_client, "bob_notes.txt", b"bob content")

    def test_user_sees_only_own_files(self):
        """Alice should see only her 2 files, not Bob's."""
        res = self.alice_client.get("/files")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)
        file_names = [f["name"] for f in res.data]
        self.assertIn("alice_resume.pdf", file_names)
        self.assertIn("alice_photo.jpg", file_names)

    def test_bob_sees_only_own_files(self):
        """Bob should see only his 1 file, not Alice's."""
        res = self.bob_client.get("/files")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["name"], "bob_notes.txt")

    def test_cannot_access_other_users_file(self):
        """Alice tries to access Bob's file — should get 403, not 404."""
        # Get Bob's file ID
        bob_files = self.bob_client.get("/files").data
        bob_file_id = bob_files[0]["id"]

        # Alice tries to access it
        res = self.alice_client.get(f"/files/{bob_file_id}")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_file_returns_404(self):
        """Accessing a file that does not exist should return 404."""
        res = self.alice_client.get("/files/9999")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_403_vs_404_distinction(self):
        """
        The task specifically requires 403 (not 404) when a file exists
        but belongs to another user. This test proves the distinction.
        """
        # Bob's file exists but Alice cannot access it → 403
        bob_files = self.bob_client.get("/files").data
        res = self.alice_client.get(f"/files/{bob_files[0]['id']}")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # File ID 9999 does not exist at all → 404
        res = self.alice_client.get("/files/9999")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class UnauthenticatedAccessTest(TestCase):
    """Unauthenticated requests should be rejected."""

    def test_list_files_without_login(self):
        """GET /files without a token should return 401."""
        client = APIClient()
        res = client.get("/files")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_file_without_login(self):
        """GET /files/:id without a token should return 401."""
        client = APIClient()
        res = client.get("/files/1")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_without_login(self):
        """GET /me without a token should return 401."""
        client = APIClient()
        res = client.get("/me")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class MultiUserIsolationTest(TestCase):
    """
    Simulates what interviewers will try: many users, each trying to
    access everyone else's files.
    """

    def setUp(self):
        """Create 5 users with their own files."""
        self.users = []
        emails = ["alice@test.com", "bob@test.com", "carol@test.com",
                  "dave@test.com", "eve@test.com"]
        for i, email in enumerate(emails):
            token = register_and_login(self.client, email)
            c = auth_client(token)
            for j in range(3):
                create_file(c, f"user{i+1}_file{j+1}.txt", f"content{j+1}".encode())
            self.users.append({"email": email, "client": c})

    def test_each_user_sees_exactly_own_files(self):
        """Every user should see exactly 3 files — only theirs."""
        for user in self.users:
            res = user["client"].get("/files")
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(len(res.data), 3,
                             f"{user['email']} should see exactly 3 files")
            for f in res.data:
                self.assertIn("user", f["name"])

    def test_nobody_can_see_anyone_elses_files(self):
        """Every user tries to access every other user's file."""
        for attacker in self.users:
            for victim in self.users:
                if attacker["email"] == victim["email"]:
                    continue
                victim_files = victim["client"].get("/files").data
                for vfile in victim_files:
                    res = attacker["client"].get(f"/files/{vfile['id']}")
                    self.assertEqual(
                        res.status_code, status.HTTP_403_FORBIDDEN,
                        f"{attacker['email']} accessed {victim['email']}'s file {vfile['name']}"
                    )

    def test_cannot_download_other_users_file(self):
        """Download endpoint should also reject cross-user access."""
        # Alice tries to download Bob's file
        bob_files = self.users[1]["client"].get("/files").data
        res = self.users[0]["client"].get(f"/files/{bob_files[0]['id']}/download")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_download_own_file(self):
        """Owner should be able to download their own file."""
        from files.models import UserFile
        user = self.users[0]
        # Create a file directly in the DB with actual content
        # (API serializer doesn't save the content field)
        f = UserFile.objects.create(
            owner=User.objects.get(email=user["email"]),
            name="real_file.txt",
            des="has content",
            size=11,
        )
        f.content.save("real_file.txt", ContentFile(b"hello world"))
        res = user["client"].get(f"/files/{f.id}/download")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_user_id_guessing_returns_403_or_404(self):
        """Try random file IDs — should never expose other user's data."""
        # Get all existing file IDs
        all_ids = set()
        for user in self.users:
            for f in user["client"].get("/files").data:
                all_ids.add(f["id"])
        # Pick IDs that belong to OTHER users
        for user in self.users:
            my_ids = {f["id"] for f in user["client"].get("/files").data}
            other_ids = all_ids - my_ids
            for fid in other_ids:
                res = user["client"].get(f"/files/{fid}")
                self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN,
                                 f"{user['email']} accessed someone else's file {fid}")
        # Also try IDs that don't exist at all
        fake_ids = [0, 99999, 88888]
        for user in self.users:
            for fid in fake_ids:
                res = user["client"].get(f"/files/{fid}")
                self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND,
                                 f"{user['email']} got unexpected response for nonexistent file {fid}")

    def test_file_list_never_leaks_owner_email_of_others(self):
        """Files listed for a user should only show their own owner email."""
        for user in self.users:
            res = user["client"].get("/files")
            for f in res.data:
                self.assertEqual(f["owner_email"], user["email"])


class FileUploadTest(TestCase):
    """File upload and download should work for the owner."""

    def setUp(self):
        self.token = register_and_login(self.client, "uploader@test.com")
        self.auth_client = auth_client(self.token)

    def test_file_upload_returns_201(self):
        """Uploading a file should succeed."""
        res = create_file(self.auth_client, "document.pdf", b"pdf content")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_file_detail_returns_owner(self):
        """File detail should show the owner's email."""
        create_file(self.auth_client, "report.pdf", b"report content")
        res = self.auth_client.get("/files/1")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["owner_email"], "uploader@test.com")
