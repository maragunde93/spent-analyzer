import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.auth import LoginRequest, authenticate_google_user, login_local, logout
from app.config import get_settings, should_seed_development_data, validate_production_settings
from app.database import Base
from app.local_auth import hash_password
from app.models import HomeGroup, Membership, User


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.previous_env = dict(os.environ)
        os.environ["SPENT_ALLOWED_GOOGLE_EMAILS"] = '["mauro@gmail.com","mica@gmail.com"]'
        os.environ["SPENT_GOOGLE_CLIENT_ID"] = "client-id"
        os.environ["SPENT_GOOGLE_CLIENT_SECRET"] = "client-secret"
        os.environ["SPENT_SESSION_SECRET"] = "test-secret"
        os.environ["SPENT_LOCAL_USERS"] = "[]"
        get_settings.cache_clear()
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        os.environ.clear()
        os.environ.update(self.previous_env)
        get_settings.cache_clear()

    def test_allowlisted_google_user_is_created(self):
        user = authenticate_google_user(
            self.db,
            {"sub": "google-1", "email": "mauro@gmail.com", "email_verified": "true", "name": "Mauro"},
        )

        self.assertEqual(user.email, "mauro@gmail.com")
        self.assertEqual(user.google_sub, "google-1")

    def test_non_allowlisted_google_user_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            authenticate_google_user(
                self.db,
                {"sub": "google-2", "email": "other@gmail.com", "email_verified": "true", "name": "Other"},
            )

        self.assertEqual(raised.exception.status_code, 403)

    def test_existing_mauro_row_maps_to_google_login_without_changing_user_id(self):
        user = User(email="mauro@gmail.com", display_name="Mauro")
        home = HomeGroup(name="Casa")
        self.db.add_all([user, home])
        self.db.flush()
        self.db.add(Membership(user_id=user.id, home_group_id=home.id, role="owner"))
        self.db.commit()
        original_id = user.id

        mapped = authenticate_google_user(
            self.db,
            {"sub": "google-mauro", "email": "mauro@gmail.com", "email_verified": True, "name": "Mauro Google"},
        )

        membership = self.db.scalar(select(Membership).where(Membership.user_id == original_id))
        self.assertEqual(mapped.id, original_id)
        self.assertEqual(mapped.google_sub, "google-mauro")
        self.assertIsNotNone(membership)

    def test_logout_clears_session(self):
        request = SimpleNamespace(session={"user_id": 1})

        result = logout(request)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(request.session, {})

    def test_local_login_maps_configured_user_to_existing_email(self):
        password_hash = hash_password("local-password-123")
        os.environ["SPENT_LOCAL_USERS"] = (
            '[{"username":"mauro","email":"mauro@example.test","display_name":"Mauro Local","password_hash":"'
            + password_hash
            + '"}]'
        )
        get_settings.cache_clear()
        existing = User(email="mauro@example.test", display_name="Mauro")
        self.db.add(existing)
        self.db.commit()
        request = SimpleNamespace(session={})

        user = login_local(LoginRequest(username="MAURO", password="local-password-123"), request, self.db)

        self.assertEqual(user.id, existing.id)
        self.assertEqual(user.display_name, "Mauro Local")
        self.assertEqual(request.session["user_id"], existing.id)

    def test_local_login_rejects_bad_password(self):
        password_hash = hash_password("local-password-123")
        os.environ["SPENT_LOCAL_USERS"] = (
            '[{"username":"mauro","email":"mauro@example.test","display_name":"Mauro","password_hash":"'
            + password_hash
            + '"}]'
        )
        get_settings.cache_clear()

        with self.assertRaises(HTTPException) as raised:
            login_local(LoginRequest(username="mauro", password="wrong-password"), SimpleNamespace(session={}), self.db)

        self.assertEqual(raised.exception.status_code, 401)

    def test_production_rejects_test_auth(self):
        settings = get_settings()
        settings.environment = "production"
        settings.test_auth_enabled = True

        with self.assertRaises(RuntimeError):
            validate_production_settings(settings)

    def test_production_does_not_run_development_seed(self):
        settings = get_settings()
        settings.environment = "production"

        self.assertFalse(should_seed_development_data(settings))

    def test_development_runs_development_seed(self):
        settings = get_settings()
        settings.environment = "development"

        self.assertTrue(should_seed_development_data(settings))


if __name__ == "__main__":
    unittest.main()
