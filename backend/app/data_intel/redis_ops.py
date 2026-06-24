import json
import logging
from typing import Optional
from app.database_ext import RedisClient

logger = logging.getLogger("scamshield.redis_ops")
_TI_TTL = 86400
_CFG_TTL = 300


def _r() -> Optional[object]:
    return RedisClient.client()


async def get_cached_threat_domain(domain: str) -> Optional[dict]:
    r = _r()
    if r is None:
        return None
    try:
        raw = await r.get(f"ti:domain:{domain}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning("Redis get ti:domain failed: %s", e)
    return None


async def set_cached_threat_domain(domain: str, data: dict):
    r = _r()
    if r is None:
        return
    try:
        await r.setex(f"ti:domain:{domain}", _TI_TTL, json.dumps(data))
    except Exception as e:
        logger.warning("Redis set ti:domain failed: %s", e)


async def get_cached_threat_vpa(vpa: str) -> Optional[dict]:
    r = _r()
    if r is None:
        return None
    try:
        raw = await r.get(f"ti:vpa:{vpa}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning("Redis get ti:vpa failed: %s", e)
    return None


async def set_cached_threat_vpa(vpa: str, data: dict):
    r = _r()
    if r is None:
        return
    try:
        await r.setex(f"ti:vpa:{vpa}", _TI_TTL, json.dumps(data))
    except Exception as e:
        logger.warning("Redis set ti:vpa failed: %s", e)


async def get_cached_threat_phone(phone: str) -> Optional[dict]:
    r = _r()
    if r is None:
        return None
    try:
        raw = await r.get(f"ti:phone:{phone}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning("Redis get ti:phone failed: %s", e)
    return None


async def set_cached_threat_phone(phone: str, data: dict):
    r = _r()
    if r is None:
        return
    try:
        await r.setex(f"ti:phone:{phone}", _TI_TTL, json.dumps(data))
    except Exception as e:
        logger.warning("Redis set ti:phone failed: %s", e)


async def get_cached_app_config() -> Optional[dict]:
    r = _r()
    if r is None:
        return None
    try:
        raw = await r.get("cfg:app")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning("Redis get cfg:app failed: %s", e)
    return None


async def set_cached_app_config(config: dict):
    r = _r()
    if r is None:
        return
    try:
        await r.setex("cfg:app", _CFG_TTL, json.dumps(config))
    except Exception as e:
        logger.warning("Redis set cfg:app failed: %s", e)
