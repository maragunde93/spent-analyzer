from functools import lru_cache
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocalAuthUser(BaseModel):
    username: str
    email: str
    display_name: str
    password_hash: str


class Settings(BaseSettings):
    app_name: str = "Spent Analyzer"
    environment: str = "development"
    database_url: str = "sqlite:///./spent_analyzer.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    test_auth_enabled: bool = True
    public_base_url: str = "http://localhost:8080"
    public_api_base_url: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    allowed_google_emails: list[str] = []
    local_users: list[LocalAuthUser] = []
    session_secret: str = "change-me"
    session_cookie_name: str = "spent_session"
    session_cookie_path: str = "/"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    seed_demo_data: bool = True
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    gemini_timeout_seconds: float = 55.0
    fx_auto_update_enabled: bool = False
    fx_api_url: str = "https://dolarapi.com/v1/dolares/blue"
    fx_update_hour_argentina: int = 11

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SPENT_")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_production_settings(settings: Settings) -> None:
    if settings.environment.lower() != "production":
        return
    if settings.test_auth_enabled:
        raise RuntimeError("SPENT_TEST_AUTH_ENABLED must be false when SPENT_ENVIRONMENT=production")
    if settings.session_secret in {"change-me", "replace-this-for-homelab", ""}:
        raise RuntimeError("SPENT_SESSION_SECRET must be set to a strong non-default value in production")
    has_google_auth = bool(settings.google_client_id and settings.google_client_secret and settings.allowed_google_emails)
    has_local_auth = bool(settings.local_users)
    if not has_google_auth and not has_local_auth:
        raise RuntimeError("Configure either SPENT_LOCAL_USERS or Google OAuth settings in production")
