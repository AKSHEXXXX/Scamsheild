import logging
from typing import Optional

from app.analytics.posthog_client import get_posthog_client

logger = logging.getLogger("scamshield.analytics.error")


def track_db_error(
    context: str,
    error: Exception,
    user_id: str = "",
    request_id: str = "",
    endpoint: str = "",
    platform: str = "",
) -> None:
    client = get_posthog_client()
    if not client.enabled:
        return
    error_type = type(error).__name__
    error_msg = str(error) if error else "Unknown database error"
    logger.warning("database_error | context=%s | type=%s | msg=%s", context, error_type, error_msg)
    client.capture_event(
        event="database_error",
        user_id=user_id or "unknown",
        properties={
            "db_context": context,
            "error_type_detail": error_type,
        },
        request_id=request_id,
        endpoint=endpoint,
        platform=platform,
        status="failure",
        error_type=error_type,
        error_message=error_msg,
    )


def track_external_api_error(
    context: str,
    error: Exception,
    user_id: str = "",
    request_id: str = "",
    endpoint: str = "",
    platform: str = "",
    http_status: Optional[int] = None,
) -> None:
    client = get_posthog_client()
    if not client.enabled:
        return
    error_type = type(error).__name__
    error_msg = str(error) if error else "Unknown external API error"
    logger.warning("external_api_error | context=%s | type=%s | status=%s",
                   context, error_type, http_status)
    client.capture_event(
        event="external_api_error",
        user_id=user_id or "unknown",
        properties={
            "external_api_context": context,
            "error_type_detail": error_type,
        },
        request_id=request_id,
        endpoint=endpoint,
        platform=platform,
        http_status=http_status,
        status="failure",
        error_type=error_type,
        error_message=error_msg,
    )
