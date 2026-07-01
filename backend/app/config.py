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

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# SECURITY: SUPABASE_SERVICE_KEY vs SUPABASE_ANON_KEY
# - SERVICE_KEY: bypasses RLS -- NEVER expose to clients
# - ANON_KEY:   RLS enforced -- safe for mobile/web apps
# Backend uses SERVICE_KEY server-side only
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    CORS_ORIGINS: list[str] = _parse_csv_env("CORS_ORIGINS", "*")
    SENSITIVITY_THRESHOLD: int = int(os.getenv("SENSITIVITY_THRESHOLD", "70"))
    MODEL_DOWNLOAD_URL: str = os.getenv("MODEL_DOWNLOAD_URL", "")
    MODEL_DOWNLOAD_KEY: str = os.getenv("MODEL_DOWNLOAD_KEY", "")
    MODEL_DOWNLOAD_SECRET: str = os.getenv("MODEL_DOWNLOAD_SECRET", "")
    MODEL_DOWNLOAD_REGION: str = os.getenv("MODEL_DOWNLOAD_REGION", "auto")
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")

    def validate(self) -> None:
        if not self.SUPABASE_URL or not self.SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")

settings = Settings()
settings.validate()