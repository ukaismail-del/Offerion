"""Tests for Bundle U — Minimal User Auth + Session Foundation."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_app():
    from app import create_app

    # Use in-memory SQLite so each test starts with a clean DB
    _prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite://"
    try:
        app = create_app()
    finally:
        if _prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    return app


def _make_client():
    app = _make_app()
    return app, app.test_client()


def _signup(client, email="test@example.com", password="password123"):
    return client.post(
        "/signup",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _login(client, email="test@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


# ── Signup Tests ─────────────────────────────────────────────────


class TestSignup(unittest.TestCase):
    """Signup route tests."""

    def test_signup_page_renders(self):
        app, client = _make_client()
        resp = client.get("/signup")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Create Your Account", resp.data)

    def test_signup_creates_user_and_redirects(self):
        app, client = _make_client()
        resp = _signup(client, email="newuser@test.com", password="secret123")
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/dashboard", resp.headers.get("Location", ""))

    def test_signup_sets_authenticated_session(self):
        app, client = _make_client()
        _signup(client, email="auth@test.com", password="secret123")
        with client.session_transaction() as s:
            self.assertTrue(s.get("is_authenticated"))
            self.assertEqual(s.get("current_user_email"), "auth@test.com")
            self.assertIsNotNone(s.get("user_id"))

    def test_signup_stores_user_in_db(self):
        app, client = _make_client()
        _signup(client, email="dbuser@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="dbuser@test.com").first()
            self.assertIsNotNone(user)
            self.assertIsNotNone(user.password_hash)
            self.assertNotEqual(user.password_hash, "secret123")
            self.assertIsNotNone(user.created_at)

    def test_signup_hashes_password(self):
        app, client = _make_client()
        _signup(client, email="hashtest@test.com", password="mypassword")
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="hashtest@test.com").first()
            self.assertTrue(user.check_password("mypassword"))
            self.assertFalse(user.check_password("wrongpassword"))

    def test_signup_duplicate_email_blocked(self):
        app, client = _make_client()
        _signup(client, email="dup@test.com", password="secret123")
        client.get("/logout")  # must log out so second signup attempt renders form
        # Sign up again with same email
        resp = client.post(
            "/signup",
            data={"email": "dup@test.com", "password": "other123"},
            follow_redirects=True,
        )
        self.assertIn(b"already exists", resp.data)

    def test_signup_missing_email(self):
        app, client = _make_client()
        resp = client.post(
            "/signup",
            data={"email": "", "password": "secret123"},
            follow_redirects=True,
        )
        self.assertIn(b"required", resp.data)

    def test_signup_short_password(self):
        app, client = _make_client()
        resp = client.post(
            "/signup",
            data={"email": "short@test.com", "password": "abc"},
            follow_redirects=True,
        )
        self.assertIn(b"at least 6", resp.data)

    def test_signup_email_lowercased(self):
        app, client = _make_client()
        _signup(client, email="UPPER@TEST.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="upper@test.com").first()
            self.assertIsNotNone(user)

    def test_signup_redirects_if_already_authenticated(self):
        app, client = _make_client()
        _signup(client, email="redir@test.com", password="secret123")
        # Now try to visit signup page while authenticated
        resp = client.get("/signup")
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/dashboard", resp.headers.get("Location", ""))

    def test_signup_starts_trial(self):
        app, client = _make_client()
        _signup(client, email="trial@test.com", password="secret123")
        with client.session_transaction() as s:
            # New users get trial
            self.assertIn(s.get("user_tier"), ("trial", "free"))


# ── Login Tests ──────────────────────────────────────────────────


class TestLogin(unittest.TestCase):
    """Login route tests."""

    def test_login_page_renders(self):
        app, client = _make_client()
        resp = client.get("/login")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Log In", resp.data)

    def test_login_with_valid_credentials(self):
        app, client = _make_client()
        _signup(client, email="valid@test.com", password="secret123")
        client.get("/logout")
        resp = _login(client, email="valid@test.com", password="secret123")
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/dashboard", resp.headers.get("Location", ""))

    def test_login_sets_authenticated_session(self):
        app, client = _make_client()
        _signup(client, email="sesslogin@test.com", password="secret123")
        client.get("/logout")
        _login(client, email="sesslogin@test.com", password="secret123")
        with client.session_transaction() as s:
            self.assertTrue(s.get("is_authenticated"))
            self.assertEqual(s.get("current_user_email"), "sesslogin@test.com")

    def test_login_wrong_password(self):
        app, client = _make_client()
        _signup(client, email="wrong@test.com", password="secret123")
        client.get("/logout")
        resp = client.post(
            "/login",
            data={"email": "wrong@test.com", "password": "badpassword"},
            follow_redirects=True,
        )
        self.assertIn(b"Invalid email or password", resp.data)

    def test_login_nonexistent_email(self):
        app, client = _make_client()
        resp = client.post(
            "/login",
            data={"email": "nobody@test.com", "password": "secret123"},
            follow_redirects=True,
        )
        self.assertIn(b"Invalid email or password", resp.data)

    def test_login_missing_fields(self):
        app, client = _make_client()
        resp = client.post(
            "/login",
            data={"email": "", "password": ""},
            follow_redirects=True,
        )
        self.assertIn(b"required", resp.data)

    def test_login_redirects_if_already_authenticated(self):
        app, client = _make_client()
        _signup(client, email="alreadyin@test.com", password="secret123")
        resp = client.get("/login")
        self.assertIn(resp.status_code, [302, 303])


# ── Logout Tests ─────────────────────────────────────────────────


class TestLogout(unittest.TestCase):
    """Logout route tests."""

    def test_logout_clears_session(self):
        app, client = _make_client()
        _signup(client, email="logout@test.com", password="secret123")
        client.get("/logout")
        with client.session_transaction() as s:
            self.assertFalse(s.get("is_authenticated", False))
            self.assertIsNone(s.get("user_id"))

    def test_logout_redirects_to_landing(self):
        app, client = _make_client()
        _signup(client, email="logoutredir@test.com", password="secret123")
        resp = client.get("/logout", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/", resp.headers.get("Location", ""))


# ── Dashboard Protection Tests ───────────────────────────────────


class TestDashboardProtection(unittest.TestCase):
    """Protected routes redirect unauthenticated users to login."""

    def test_dashboard_requires_auth(self):
        app, client = _make_client()
        resp = client.get("/dashboard", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/login", resp.headers.get("Location", ""))

    def test_resume_preview_requires_auth(self):
        app, client = _make_client()
        resp = client.get("/resume-preview", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/login", resp.headers.get("Location", ""))

    def test_enhance_resume_requires_auth(self):
        app, client = _make_client()
        resp = client.get("/enhance-resume", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/login", resp.headers.get("Location", ""))

    def test_dashboard_accessible_after_login(self):
        app, client = _make_client()
        _signup(client, email="access@test.com", password="secret123")
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_shows_welcome_email(self):
        app, client = _make_client()
        _signup(client, email="welcome@test.com", password="secret123")
        resp = client.get("/dashboard")
        self.assertIn(b"welcome@test.com", resp.data)

    def test_dashboard_after_logout_redirects(self):
        app, client = _make_client()
        _signup(client, email="postlogout@test.com", password="secret123")
        client.get("/logout")
        resp = client.get("/dashboard", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/login", resp.headers.get("Location", ""))


# ── Public Routes Tests ──────────────────────────────────────────


class TestPublicRoutes(unittest.TestCase):
    """Public routes remain accessible without auth."""

    def test_landing_accessible(self):
        app, client = _make_client()
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_pricing_accessible(self):
        app, client = _make_client()
        resp = client.get("/pricing")
        self.assertEqual(resp.status_code, 200)

    def test_login_page_accessible(self):
        app, client = _make_client()
        resp = client.get("/login")
        self.assertEqual(resp.status_code, 200)

    def test_signup_page_accessible(self):
        app, client = _make_client()
        resp = client.get("/signup")
        self.assertEqual(resp.status_code, 200)


# ── Nav / Template Tests ─────────────────────────────────────────


class TestNavigation(unittest.TestCase):
    """Nav shows correct auth links."""

    def test_landing_shows_login_signup_when_logged_out(self):
        app, client = _make_client()
        resp = client.get("/")
        html = resp.data.decode()
        self.assertIn('href="/login"', html)
        self.assertIn('href="/signup"', html)

    def test_landing_shows_logout_when_logged_in(self):
        app, client = _make_client()
        _signup(client, email="navtest@test.com", password="secret123")
        resp = client.get("/")
        html = resp.data.decode()
        self.assertIn('href="/logout"', html)
        self.assertIn('href="/dashboard"', html)

    def test_landing_hero_cta_signup_when_logged_out(self):
        app, client = _make_client()
        resp = client.get("/")
        html = resp.data.decode()
        self.assertIn("Get Started Free", html)

    def test_landing_hero_cta_dashboard_when_logged_in(self):
        app, client = _make_client()
        _signup(client, email="heroctx@test.com", password="secret123")
        resp = client.get("/")
        html = resp.data.decode()
        self.assertIn("Go to Dashboard", html)

    def test_pricing_shows_auth_links_when_logged_out(self):
        app, client = _make_client()
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn('href="/login"', html)
        self.assertIn('href="/signup"', html)

    def test_pricing_shows_logout_when_logged_in(self):
        app, client = _make_client()
        _signup(client, email="pricenav@test.com", password="secret123")
        resp = client.get("/pricing")
        html = resp.data.decode()
        self.assertIn('href="/logout"', html)

    def test_dashboard_shows_logout_link(self):
        app, client = _make_client()
        _signup(client, email="dashnav@test.com", password="secret123")
        resp = client.get("/dashboard")
        html = resp.data.decode()
        self.assertIn('href="/logout"', html)


# ── User Model Tests ─────────────────────────────────────────────


class TestUserModel(unittest.TestCase):
    """UserIdentity auth fields and methods."""

    def test_set_and_check_password(self):
        from app.models import UserIdentity

        user = UserIdentity()
        user.set_password("testpass")
        self.assertTrue(user.check_password("testpass"))
        self.assertFalse(user.check_password("wrong"))

    def test_check_password_no_hash(self):
        from app.models import UserIdentity

        user = UserIdentity()
        self.assertFalse(user.check_password("anything"))

    def test_password_not_stored_plain(self):
        from app.models import UserIdentity

        user = UserIdentity()
        user.set_password("mypassword")
        self.assertNotEqual(user.password_hash, "mypassword")
        self.assertTrue(len(user.password_hash) > 30)

    def test_model_has_auth_fields(self):
        from app.models import UserIdentity

        user = UserIdentity()
        self.assertTrue(hasattr(user, "email"))
        self.assertTrue(hasattr(user, "password_hash"))
        self.assertTrue(hasattr(user, "is_active"))

    def test_model_has_tracking_fields(self):
        from app.models import UserIdentity

        user = UserIdentity()
        self.assertTrue(hasattr(user, "tier"))
        self.assertTrue(hasattr(user, "trial_start"))
        self.assertTrue(hasattr(user, "trial_end"))
        self.assertTrue(hasattr(user, "created_at"))

    def test_is_active_default(self):
        app, client = _make_client()
        _signup(client, email="active@test.com", password="secret123")
        with app.app_context():
            from app.models import UserIdentity

            user = UserIdentity.query.filter_by(email="active@test.com").first()
            self.assertTrue(user.is_active)


# ── Backward Compatibility Tests ─────────────────────────────────


class TestBackwardCompatibility(unittest.TestCase):
    """Existing test patterns (session-seeded user_id) still work in TESTING mode."""

    def test_session_seeded_user_reaches_dashboard(self):
        """Existing tests set user_id without is_authenticated and should pass."""
        app = _make_app()
        client = app.test_client()
        with app.app_context():
            from app.models import UserIdentity
            from app.db import db

            if not UserIdentity.query.filter_by(id="compat-user").first():
                user = UserIdentity(id="compat-user", tier="elite")
                db.session.add(user)
                db.session.commit()

        with client.session_transaction() as s:
            s["user_id"] = "compat-user"
            s["user_tier"] = "elite"

        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_pricing_works_without_any_session(self):
        app, client = _make_client()
        resp = client.get("/pricing")
        self.assertEqual(resp.status_code, 200)


# ── Full Flow Integration Test ───────────────────────────────────


class TestFullAuthFlow(unittest.TestCase):
    """End-to-end signup → dashboard → logout → login → dashboard flow."""

    def test_complete_flow(self):
        app, client = _make_client()

        # 1. Landing accessible
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)

        # 2. Signup
        resp = _signup(client, email="flow@test.com", password="secret123")
        self.assertIn(resp.status_code, [302, 303])

        # 3. Dashboard accessible
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"flow@test.com", resp.data)

        # 4. Logout
        resp = client.get("/logout", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])

        # 5. Dashboard blocked
        resp = client.get("/dashboard", follow_redirects=False)
        self.assertIn(resp.status_code, [302, 303])
        self.assertIn("/login", resp.headers.get("Location", ""))

        # 6. Login
        resp = _login(client, email="flow@test.com", password="secret123")
        self.assertIn(resp.status_code, [302, 303])

        # 7. Dashboard accessible again
        resp = client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"flow@test.com", resp.data)


if __name__ == "__main__":
    unittest.main()
