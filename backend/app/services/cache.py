import json
import logging

import redis.asyncio as redis

from app.config import settings
from app.services.reservations import calculate_total_revenue

logger = logging.getLogger(__name__)
redis_client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)


async def get_revenue_summary(property_id, tenant_id, year, month, property_timezone, db_session):
    cache_key = "revenue:v2:" + json.dumps(
        [tenant_id, property_id, year, month, property_timezone], separators=(",", ":")
    )
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except (redis.RedisError, ValueError):
        logger.warning("Revenue cache unavailable; reading reservations")

    result = await calculate_total_revenue(
        property_id, tenant_id, year, month, property_timezone, db_session
    )
    try:
        await redis_client.setex(cache_key, 300, json.dumps(result))
    except redis.RedisError:
        logger.warning("Revenue cache unavailable; returning calculated totals")
    return result
