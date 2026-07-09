import logging
import os
import time
import uuid
from typing import Optional

from posthog import Posthog

logger = logging.getLogger("scamshield.analytics")


class PosthogClient:
    """Thread-safe PostHog wrapper that enriches every event with common metadata.

    Uses the instance-based Posthog() constructor instead of the deprecated
    module-level API.  Never raises — all failures are logged and swallowed.
    """

    def __init__(self) -> None:
        self._client: Optional[Posthog] = None
        self._distinct_id: Optional[str] = None
        self._host: str = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
        self._api_key: str = os.getenv("POSTHOG_PROJECT_TOKEN", "")
        self._app_version: str = os.getenv("APP_VERSION", "2.1.0")

    # ── lifecycle ────────────────────────────────────────────────

    def setup(self) -> None:
        if not self._api_key:
            logger.warning("POSTHOG_PROJECT_TOKEN is not set — analytics disabled")
            return
        self._client = Posthog(
            self._api_key,
            host=self._host,
            enable_exception_autocapture=True,
        )
        logger.info("PosthogClient initialized (host=%s)", self._host)

    def shutdown(self) -> None:
        if self._client is not None:
            try:
                self._client.shutdown()
            except Exception:
                pass

    @property
    def enabled(self) -> bool:
        return self._client is not None

    # ── identity ─────────────────────────────────────────────────

    def identify(self, user_id: str, properties: Optional[dict] = None) -> None:
        if not self.enabled:
            return
        self._distinct_id = user_id
        try:
            self._client.set(distinct_id=user_id, properties=properties or {})
        except Exception as exc:
            logger.debug("PostHog identify failed: %s", exc)

    def reset(self) -> None:
        self._distinct_id = None

    # ── capture ──────────────────────────────────────────────────

    def capture_event(
        self,
        event: str,
        user_id: str,
        properties: Optional[dict] = None,
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        platform: Optional[str] = None,
        http_status: Optional[int] = None,
        processing_time_ms: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        threat_score: Optional[int] = None,
        confidence_score: Optional[float] = None,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        status: Optional[str] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return

        enriched: dict = {
            "request_id": request_id or "",
            "endpoint": endpoint or "",
            "platform": (platform or "unknown").lower(),
            "app_version": self._app_version,
        }
        if http_status is not None:
            enriched["http_status"] = http_status
        if processing_time_ms is not None:
            enriched["processing_time_ms"] = processing_time_ms
        if response_time_ms is not None:
            enriched["response_time_ms"] = response_time_ms
        if threat_score is not None:
            enriched["threat_score"] = threat_score
        if confidence_score is not None:
            enriched["confidence_score"] = round(confidence_score, 4)
        if model_name is not None:
            enriched["model_name"] = model_name
        if model_version is not None:
            enriched["model_version"] = model_version
        if status is not None:
            enriched["status"] = status
        if error_type is not None:
            enriched["error_type"] = error_type
        if error_message is not None:
            from app.logging_utils import sanitize_pii
            enriched["error_message"] = sanitize_pii(error_message)[:500]
        if properties:
            enriched.update(properties)

        try:
            self._client.capture(event, distinct_id=user_id, properties=enriched)
        except Exception as exc:
            logger.debug("PostHog capture failed for event=%s: %s", event, exc)

    # ── convenience helpers ──────────────────────────────────────

    def capture_scan_event(
        self,
        event: str,
        user_id: str,
        channel: str,
        verdict: str,
        score: int,
        latency_ms: int,
        request_id: str,
        endpoint: str,
        platform: str,
        agents_used: Optional[list[str]] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        extra_properties: Optional[dict] = None,
    ) -> None:
        props: dict = {
            "channel": channel,
            "verdict": verdict,
            "score": score,
            "latency_ms": latency_ms,
        }
        if agents_used:
            props["agents_used"] = agents_used
        if extra_properties:
            props.update(extra_properties)
        self.capture_event(
            event=event,
            user_id=user_id,
            properties=props,
            request_id=request_id,
            endpoint=endpoint,
            platform=platform,
            processing_time_ms=latency_ms,
            response_time_ms=latency_ms,
            threat_score=score,
            status="error" if error_type else "success",
            error_type=error_type,
            error_message=error_message,
        )

    def capture_ocr_event(
        self,
        event: str,
        user_id: str,
        method: str,
        confidence: float,
        char_count: int,
        fallback_used: bool,
        latency_ms: int,
        request_id: str,
        endpoint: str,
        platform: str,
        error_message: Optional[str] = None,
    ) -> None:
        props: dict = {
            "ocr_method": method,
            "ocr_confidence": round(confidence, 2),
            "ocr_char_count": char_count,
            "ocr_fallback": fallback_used,
            "latency_ms": latency_ms,
        }
        self.capture_event(
            event=event,
            user_id=user_id,
            properties=props,
            request_id=request_id,
            endpoint=endpoint,
            platform=platform,
            processing_time_ms=latency_ms,
            confidence_score=confidence,
            status="error" if error_message else "success",
            error_type="ocr_failed" if error_message else None,
            error_message=error_message,
        )


_client: Optional[PosthogClient] = None


def get_posthog_client() -> PosthogClient:
    global _client
    if _client is None:
        _client = PosthogClient()
    return _client


def setup_posthog() -> PosthogClient:
    client = get_posthog_client()
    client.setup()
    return client


def close_posthog() -> None:
    client = get_posthog_client()
    client.shutdown()
