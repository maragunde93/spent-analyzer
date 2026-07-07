from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Spent Analyzer"
    environment: str = "development"
    database_url: str = "sqlite:///./spent_analyzer.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    test_auth_enabled: bool = True
    google_client_id: str | None = None
    google_client_secret: str | None = None
    session_secret: str = "change-me"
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
