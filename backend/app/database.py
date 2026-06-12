from functools import lru_cache
from supabase import create_client, Client
from app.config import settings

@lru_cache(maxsize=None)
def _get_supabase() -> Client:
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY
    )

class _LazyClient:
    def __getattr__(self, name):
        return getattr(_get_supabase(), name)

supabase: Client = _LazyClient()  # type: ignore[assignment]