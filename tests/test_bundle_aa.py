"""Tests for Bundle AA — Auth hardening and account safety."""

import os
import re
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_app():
    from app import create_app

    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite://"
    try:
        app = create_app(testing=True)
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


def _make_client():
    app = _make_app()
    return app, app.test_client()


def _signup(client, email="aa@example.com", password="password123"):
    return client.post(
        "/signup",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _login(client, email="aa@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _extract_first_link(html, path_prefix):
    pattern = rf'href="([^"]*{re.escape(path_prefix)}[^"]*)"'
    match = re.search(pattern, html)
    return match.group(1) if match else None


class TestPasswordResetFlow(unittest.TestCase):
    def test_forgot_password_page_renders(self):
        app, client = _make_client()
        resp = client.get("/forgot-password")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Reset Your Password", resp.data)

    def test_password_reset_round_trip(self):
        app, client = _make_client()
        _signup(client, email="resetflow@test.com", password="oldpass123")
        client.get("/logout")

        resp = client.post(
            "/forgot-password",
            data={"email": "resetflow@test.com"},
            follow_redirects=True,
        )
        html = resp.data.decode()
        self.assertIn("reset link has been sent", html)

        reset_link = _extract_first_link(html, "/reset-password/")
        self.assertIsNotNone(reset_link)

        post_resp = client.post(
            reset_link,
            data={"password": "newpass123", "confirm_password": "newpass123"},
            follow_redirects=False,
        )
        self.assertIn(post_resp.status_code, (302, 303))
        self.assertIn("/login?reset=success", post_resp.headers.get("Location", ""))

        old_login = _login(client, email="resetflow@test.com", password="oldpass123")
        self.assertIn(old_login.status_code, (200, 302, 303))
        if old_login.status_code == 200:
            self.assertIn(b"Invalid email or password", old_login.data)

        client.get("/logout")
        new_login = _login(client, email="resetflow@test.com", password="newpass123")
        self.assertIn(new_login.status_code, (302, 303))
        self.assertIn("/dashboard", new_login.headers.get("Location", ""))

    def test_invalid_reset_token_is_handled(self):
        app, client = _make_client()
        resp = client.get("/reset-password/not-a-valid-token")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"invalid or has expired", resp.data)

    def test_expired_reset_token_is_handled(self):
        app, client = _make_client()
        _signup(client, email="expiredreset@test.com", password="oldpass123")

        with app.app_context():
            from app.db import db
            from app.models import UserIdentity
            from werkzeug.security import generate_password_hash

            user = UserIdentity.query.filter_by(email="expiredreset@test.com").first()
            nonce = "expired-nonce"
            user.password_reset_token_hash = generate_password_hash(nonce)
            user.password_reset_expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.session.commit()
            token = f"{user.id}.{nonce}"

        resp = client.get(f"/reset-password/{token}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"invalid or has expired", resp.data)


class TestEmailVerification(unittest.TestCase):
    def test_signup_sets_user_unverified(self):
        app, client = _make_client()
        _signup(client, email="verify-state@test.com", password="secret123")

        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="verify-state@test.com").first()
            self.assertIsNotNone(user)
            self.assertFalse(bool(user.email_verified))

    def test_verification_link_marks_user_verified(self):
        app, client = _make_client()
        _signup(client, email="verify-link@test.com", password="secret123")

        dash = client.get("/dashboard")
        html = dash.data.decode()
        verify_link = _extract_first_link(html, "/verify-email/")
        self.assertIsNotNone(verify_link)

        resp = client.get(verify_link, follow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn("/login?verified=1", resp.headers.get("Location", ""))

        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="verify-link@test.com").first()
            self.assertTrue(bool(user.email_verified))
            self.assertIsNotNone(user.email_verified_at)


class TestAuthRateLimit(unittest.TestCase):
    def test_login_rate_limit_blocks_burst_attempts(self):
        app, client = _make_client()
        _signup(client, email="ratelimit-login@test.com", password="secret123")
        client.get("/logout")

        blocked = False
        for _ in range(10):
            resp = client.post(
                "/login",
                data={"email": "ratelimit-login@test.com", "password": "wrongpass"},
                follow_redirects=True,
            )
            if b"Too many login attempts" in resp.data:
                blocked = True
                break
        self.assertTrue(blocked)

    def test_forgot_password_rate_limit_blocks_burst_attempts(self):
        app, client = _make_client()
        _signup(client, email="ratelimit-forgot@test.com", password="secret123")
        client.get("/logout")

        blocked = False
        for _ in range(8):
            resp = client.post(
                "/forgot-password",
                data={"email": "ratelimit-forgot@test.com"},
                follow_redirects=True,
            )
            if b"Too many reset requests" in resp.data:
                blocked = True
                break
        self.assertTrue(blocked)


if __name__ == "__main__":
    unittest.main()
