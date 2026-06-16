import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    CORS_ORIGINS: list[str] = ["*"]
    SENSITIVITY_THRESHOLD: int = int(os.getenv("SENSITIVITY_THRESHOLD", "70"))
    MODEL_DOWNLOAD_URL: str = os.getenv("MODEL_DOWNLOAD_URL", "")
    MODEL_DOWNLOAD_KEY: str = os.getenv("MODEL_DOWNLOAD_KEY", "")
    MODEL_DOWNLOAD_SECRET: str = os.getenv("MODEL_DOWNLOAD_SECRET", "")
    MODEL_DOWNLOAD_REGION: str = os.getenv("MODEL_DOWNLOAD_REGION", "auto")

settings = Settings()