import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = Path(os.getenv("MODEL_DIR", str(BASE_DIR / "app" / "ml" / "artifacts")))


def _parse_csv_env(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_cors_origins() -> list[str]:
    # Keep production-safe defaults when env is missing.
    origins = _parse_csv_env("CORS_ORIGINS", "")
    if origins:
        return origins
    return [
        "https://unique-cat-admin.up.railway.app",
        "http://localhost:3000",
    ]

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# SECURITY: SUPABASE_SERVICE_KEY vs SUPABASE_ANON_KEY
# - SERVICE_KEY: bypasses RLS -- NEVER expose to clients
# - ANON_KEY:   RLS enforced -- safe for mobile/web apps
# Backend uses SERVICE_KEY server-side only
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    CORS_ORIGINS: list[str] = _parse_cors_origins()
    SENSITIVITY_THRESHOLD: int = int(os.getenv("SENSITIVITY_THRESHOLD", "70"))
    VERSION: str = os.getenv("APP_VERSION", "2.1.0")
    MODEL_DOWNLOAD_URL: str = os.getenv("MODEL_DOWNLOAD_URL", "")
    MODEL_DOWNLOAD_KEY: str = os.getenv("MODEL_DOWNLOAD_KEY", "")
    MODEL_DOWNLOAD_SECRET: str = os.getenv("MODEL_DOWNLOAD_SECRET", "")
    MODEL_DOWNLOAD_REGION: str = os.getenv("MODEL_DOWNLOAD_REGION", "auto")
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")
    POSTHOG_PROJECT_TOKEN: str = os.getenv("POSTHOG_PROJECT_TOKEN", "")
    POSTHOG_HOST: str = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")

    def validate(self) -> None:
        if not self.SUPABASE_URL or not self.SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")

settings = Settings()
settings.validate()