"""Rate limiting"""

from typing import Tuple, Optional
import redis.asyncio as aioredis
import time

from bot.config import config


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, redis_url: str = config.redis.url):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
        self.user_requests = config.rate_limit.user_requests
        self.user_window = config.rate_limit.user_window
        self.global_requests = config.rate_limit.global_requests
        self.global_window = config.rate_limit.global_window
    
    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            self._redis = await aioredis.from_url(self.redis_url, decode_responses=False)
        return self._redis
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
    
    async def check_limit(self, user_id: int) -> Tuple[bool, Optional[int]]:
        """
        Check if user can make request
        
        Returns:
            (allowed, retry_after_seconds)
        """
        redis = await self._get_redis()
        
        # Check user limit
        user_key = f"ratelimit:user:{user_id}"
        user_count = await redis.get(user_key)
        
        if user_count and int(user_count) >= self.user_requests:
            ttl = await redis.ttl(user_key)
            return False, ttl if ttl > 0 else self.user_window
        
        # Check global limit
        global_key = "ratelimit:global"
        global_count = await redis.get(global_key)
        
        if global_count and int(global_count) >= self.global_requests:
            ttl = await redis.ttl(global_key)
            return False, ttl if ttl > 0 else self.global_window
        
        return True, None
    
    async def consume_token(self, user_id: int) -> None:
        """Consume a rate limit token"""
        redis = await self._get_redis()
        
        # Increment user counter
        user_key = f"ratelimit:user:{user_id}"
        pipe = redis.pipeline()
        pipe.incr(user_key)
        pipe.expire(user_key, self.user_window)
        
        # Increment global counter
        global_key = "ratelimit:global"
        pipe.incr(global_key)
        pipe.expire(global_key, self.global_window)
        
        await pipe.execute()
    
    async def reset_user_limit(self, user_id: int) -> None:
        """Reset rate limit for a user (admin function)"""
        redis = await self._get_redis()
        user_key = f"ratelimit:user:{user_id}"
        await redis.delete(user_key)
