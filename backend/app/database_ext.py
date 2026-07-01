import os
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger("scamshield.db")

class MongoDBClient:
    _client: Optional[object] = None
    _db: Optional[object] = None

    @classmethod
    def connect(cls, uri: Optional[str] = None):
        uri = uri or os.getenv("MONGODB_URI") or os.getenv("MONGO_URL") or os.getenv("MONGO_PUBLIC_URL", "")
        if not uri:
            logger.warning("MONGODB_URI / MONGO_URL not set — MongoDB not available")
            return False
        try:
            import pymongo
            cls._client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
            cls._client.admin.command("ping")
            db_name = os.getenv("MONGODB_DB", "scamshield")
            cls._db = cls._client[db_name]
            logger.info("Connected to MongoDB: %s/%s", uri.split("@")[-1].split("/")[0], db_name)
            return True
        except Exception as e:
            logger.warning("MongoDB connection failed: %s", e)
            cls._client = None
            cls._db = None
            return False

    @classmethod
    def db(cls):
        return cls._db

    @classmethod
    def is_connected(cls) -> bool:
        return cls._db is not None

    @classmethod
    def close(cls):
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None

class RedisClient:
    _client: Optional[object] = None

    @classmethod
    def connect(cls, url: Optional[str] = None):
        url = url or os.getenv("REDIS_URL", "")
        if not url:
            logger.warning("REDIS_URL not set — Redis not available")
            return False
        try:
            import redis.asyncio as aioredis
            cls._client = aioredis.from_url(url, decode_responses=True)
            logger.info("Connected to Redis: %s", url.split("@")[-1].split("/")[0])
            return True
        except Exception as e:
            logger.warning("Redis connection failed: %s", e)
            cls._client = None
            return False

    @classmethod
    def client(cls):
        return cls._client

    @classmethod
    def is_connected(cls) -> bool:
        return cls._client is not None

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            cls._client = None

def ensure_indexes():
    db = MongoDBClient.db()
    if db is None:
        return
    from app.data_intel.mongo_schemas import MONGODB_COLLECTIONS
    for name, spec in MONGODB_COLLECTIONS.items():
        try:
            existing = list(db[name].list_indexes())
            existing_names = {idx["name"] for idx in existing}
            for idx_spec in spec.get("indexes", []):
                keys = idx_spec["keys"]
                idx_name = "_".join(f"{k}_{d}" for k, d in keys)
                if idx_name not in existing_names:
                    kwargs = {"unique": idx_spec.get("unique", False)}
                    db[name].create_index(keys, name=idx_name, **kwargs)
                    logger.debug("Created index %s on %s", idx_name, name)
            if spec.get("ttl_days"):
                ttl_key = "created_at"
                ttl_name = f"{ttl_key}_ttl"
                if ttl_name not in existing_names:
                    db[name].create_index(ttl_key, name=ttl_name, expireAfterSeconds=spec["ttl_days"] * 86400)
                    logger.debug("Created TTL index on %s (%d days)", name, spec["ttl_days"])
        except Exception as e:
            logger.warning("Index setup for %s skipped: %s", name, e)

def connect_databases():
    mongo_ok = MongoDBClient.connect()
    redis_ok = RedisClient.connect()
    status = []
    if mongo_ok:
        ensure_indexes()
        status.append("MongoDB: connected")
    else:
        status.append("MongoDB: not configured (set MONGODB_URI or MONGO_URL)")
    if redis_ok:
        status.append("Redis: connected")
    else:
        status.append("Redis: not configured (REDIS_URL not set)")
    logger.info("Database status: %s", " | ".join(status))
    return mongo_ok, redis_ok

def close_databases():
    MongoDBClient.close()
    import asyncio
    try:
        asyncio.run(RedisClient.close())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(RedisClient.close())
