import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.analytics.posthog_client import get_posthog_client

logger = logging.getLogger("scamshield.middleware.request_tracking")


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """Assigns a unique request_id to every request, measures total
    latency, and captures api_request_completed / api_request_failed
    events to PostHog when a user is authenticated."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.start_time = time.time()

        response: Response = await call_next(request)

        elapsed_ms = int(round((time.time() - request.state.start_time) * 1000))
        endpoint = request.url.path
        method = request.method
        status_code = response.status_code
        success = status_code < 500

        response.headers["X-Request-ID"] = request_id

        user_id = getattr(request.state, "user_id", None) or ""
        platform = getattr(request.state, "platform", "unknown")
        agent_results = getattr(request.state, "agent_results", None)

        try:
            client = get_posthog_client()
            if client.enabled and user_id:
                event = "api_request_completed" if success else "api_request_failed"
                client.capture_event(
                    event=event,
                    user_id=user_id,
                    properties={
                        "method": method,
                        "latency_ms": elapsed_ms,
                        "success": success,
                    },
                    request_id=request_id,
                    endpoint=endpoint,
                    platform=platform,
                    http_status=status_code,
                    response_time_ms=elapsed_ms,
                    status="success" if success else "failure",
                )
        except Exception as exc:
            logger.debug("RequestTrackingMiddleware capture failed: %s", exc)

        return response
