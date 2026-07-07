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

from app.api.auth import authenticate_google_user, logout
from app.config import get_settings, validate_production_settings
from app.database import Base
from app.models import HomeGroup, Membership, User


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.previous_env = dict(os.environ)
        os.environ["SPENT_ALLOWED_GOOGLE_EMAILS"] = '["mauro@gmail.com","mica@gmail.com"]'
        os.environ["SPENT_GOOGLE_CLIENT_ID"] = "client-id"
        os.environ["SPENT_GOOGLE_CLIENT_SECRET"] = "client-secret"
        os.environ["SPENT_SESSION_SECRET"] = "test-secret"
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

    def test_production_rejects_test_auth(self):
        settings = get_settings()
        settings.environment = "production"
        settings.test_auth_enabled = True

        with self.assertRaises(RuntimeError):
            validate_production_settings(settings)


if __name__ == "__main__":
    unittest.main()
