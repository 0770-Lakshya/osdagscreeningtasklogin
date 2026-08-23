"""
Tests for authentication: register, login, logout, rate limiting.

Run with: python manage.py test users
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import FailedLoginAttempt, User


class RegisterTest(TestCase):
    """Registration should create a user and return tokens."""

    def test_register_returns_201(self):
        res = self.client.post(
            "/register",
            {"email": "new@test.com", "password": "StrongPass1!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", res.data)
        self.assertTrue(User.objects.filter(email="new@test.com").exists())

    def test_register_duplicate_email_is_rejected(self):
        """Registering the same email twice should fail."""
        self.client.post(
            "/register",
            {"email": "dup@test.com", "password": "StrongPass1!"},
            format="json",
        )
        res = self.client.post(
            "/register",
            {"email": "dup@test.com", "password": "StrongPass1!"},
            format="json",
        )
        # DRF returns 400 (serializer validation) for unique constraint
        self.assertIn(res.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT])

    def test_register_short_password_fails(self):
        res = self.client.post(
            "/register",
            {"email": "weak@test.com", "password": "123"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTest(TestCase):
    """Login should return tokens for valid credentials."""

    def setUp(self):
        self.client.post(
            "/register",
            {"email": "alice@test.com", "password": "StrongPass1!"},
            format="json",
        )

    def test_login_returns_200_with_token(self):
        res = self.client.post(
            "/login",
            {"email": "alice@test.com", "password": "StrongPass1!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("token", res.data)

    def test_login_wrong_password_returns_401(self):
        res = self.client.post(
            "/login",
            {"email": "alice@test.com", "password": "WrongPass!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_wrong_email_returns_401(self):
        """Should return 401 — never reveal whether the email exists."""
        res = self.client.post(
            "/login",
            {"email": "nobody@test.com", "password": "StrongPass1!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_same_error_for_wrong_email_and_wrong_password(self):
        """Both cases should return the same generic error message."""
        res_wrong_pass = self.client.post(
            "/login",
            {"email": "alice@test.com", "password": "WrongPass!"},
            format="json",
        )
        res_wrong_email = self.client.post(
            "/login",
            {"email": "nobody@test.com", "password": "StrongPass1!"},
            format="json",
        )
        self.assertEqual(res_wrong_pass.data["detail"], res_wrong_email.data["detail"])


class RateLimitingTest(TestCase):
    """After 5 failed login attempts, the account should be locked out."""

    def setUp(self):
        self.client.post(
            "/register",
            {"email": "victim@test.com", "password": "StrongPass1!"},
            format="json",
        )

    def test_lockout_after_5_failures(self):
        # Fail 5 times
        for _ in range(5):
            self.client.post(
                "/login",
                {"email": "victim@test.com", "password": "WrongPass!"},
                format="json",
            )

        # 6th attempt should be locked out
        res = self.client.post(
            "/login",
            {"email": "victim@test.com", "password": "WrongPass!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class MeEndpointTest(TestCase):
    """GET /me should return the authenticated user's data."""

    def setUp(self):
        res = self.client.post(
            "/register",
            {"email": "me@test.com", "password": "StrongPass1!"},
            format="json",
        )
        self.token = res.data["token"]

    def test_me_returns_user_data(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        res = client.get("/me")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["email"], "me@test.com")

    def test_me_without_token_returns_401(self):
        res = self.client.get("/me")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutTest(TestCase):
    """Logout should invalidate the access token."""

    def setUp(self):
        res = self.client.post(
            "/register",
            {"email": "logout@test.com", "password": "StrongPass1!"},
            format="json",
        )
        self.token = res.data["token"]

    def test_logout_returns_200(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        res = client.post("/logout")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_token_invalidated_after_logout(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        client.post("/logout")

        # Try to use the same token after logout
        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        res = client2.get("/me")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
