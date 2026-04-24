from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development")
    app_base_url: str = Field(default="http://localhost:8000")
    frontend_base_url: str = Field(default="http://localhost:5173")

    supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: str = ""

    openai_api_key: str = ""
    openai_model_match: str = "gpt-4o-mini"
    openai_model_email: str = "gpt-4o"
    openai_model_embedding: str = "text-embedding-3-small"

    user_monthly_budget_usd: float = 0.5
    global_monthly_budget_usd: float = 50.0
    coord_email_cooldown_days: int = 30
    cv_retention_days: int = 90
    opt_out_jwt_secret: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
