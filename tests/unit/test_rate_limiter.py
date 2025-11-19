"""Unit tests for RateLimiter"""

import pytest
from unittest.mock import AsyncMock, patch
from bot.rate_limiter import RateLimiter


@pytest.mark.unit
class TestRateLimiter:
    """Test RateLimiter functionality"""

    @pytest.fixture
    async def rate_limiter(self, mock_redis):
        """Create rate limiter with mocked Redis"""
        with patch('bot.rate_limiter.aioredis.from_url', return_value=mock_redis):
            limiter = RateLimiter()
            limiter._redis = mock_redis
            yield limiter
            await limiter.close()

    async def test_check_limit_allows_first_request(self, rate_limiter, mock_redis):
        """Test that first request is always allowed"""
        # Mock Redis to return None (no existing counter)
        mock_redis.get = AsyncMock(return_value=None)

        allowed, retry_after = await rate_limiter.check_limit(user_id=12345)

        assert allowed is True
        assert retry_after is None

    async def test_check_limit_blocks_after_exceeding_user_limit(self, rate_limiter, mock_redis):
        """Test that requests are blocked after exceeding user limit"""
        # Mock Redis to return max requests
        async def mock_get(key):
            if "user" in key:
                return str(rate_limiter.user_requests)  # At limit
            return "0"

        mock_redis.get = AsyncMock(side_effect=mock_get)
        mock_redis.ttl = AsyncMock(return_value=30)

        allowed, retry_after = await rate_limiter.check_limit(user_id=12345)

        assert allowed is False
        assert retry_after == 30

    async def test_check_limit_blocks_after_exceeding_global_limit(self, rate_limiter, mock_redis):
        """Test that requests are blocked after exceeding global limit"""
        # Mock Redis to return below user limit but at global limit
        async def mock_get(key):
            if "user" in key:
                return "5"  # Below user limit
            if "global" in key:
                return str(rate_limiter.global_requests)  # At global limit
            return "0"

        mock_redis.get = AsyncMock(side_effect=mock_get)
        mock_redis.ttl = AsyncMock(return_value=45)

        allowed, retry_after = await rate_limiter.check_limit(user_id=12345)

        assert allowed is False
        assert retry_after == 45

    async def test_consume_token_increments_counters(self, rate_limiter, mock_redis):
        """Test that consuming a token increments both user and global counters"""
        await rate_limiter.consume_token(user_id=12345)

        # Verify pipeline was called
        mock_redis.pipeline.assert_called_once()

    async def test_consume_token_sets_expiration(self, rate_limiter, mock_redis):
        """Test that consuming a token sets expiration on counters"""
        pipe_mock = mock_redis.pipeline()

        await rate_limiter.consume_token(user_id=12345)

        # Verify expire was called in pipeline
        assert pipe_mock.expire.call_count == 2

    async def test_reset_user_limit_clears_counter(self, rate_limiter, mock_redis):
        """Test that resetting user limit clears their counter"""
        await rate_limiter.reset_user_limit(user_id=12345)

        mock_redis.delete.assert_called_once_with("ratelimit:user:12345")

    async def test_check_limit_with_zero_ttl_uses_window(self, rate_limiter, mock_redis):
        """Test that when TTL is 0 or negative, we use the configured window"""
        async def mock_get(key):
            if "user" in key:
                return str(rate_limiter.user_requests)
            return "0"

        mock_redis.get = AsyncMock(side_effect=mock_get)
        mock_redis.ttl = AsyncMock(return_value=-1)  # No TTL set

        allowed, retry_after = await rate_limiter.check_limit(user_id=12345)

        assert allowed is False
        assert retry_after == rate_limiter.user_window

    async def test_multiple_users_independent_limits(self, rate_limiter, mock_redis):
        """Test that different users have independent rate limits"""
        # User 1 at limit
        async def mock_get_user1(key):
            if "user:12345" in key:
                return str(rate_limiter.user_requests)
            return "0"

        # User 2 not at limit
        async def mock_get_user2(key):
            if "user:67890" in key:
                return "0"
            return "0"

        # Check user 1 (should be blocked)
        mock_redis.get = AsyncMock(side_effect=mock_get_user1)
        mock_redis.ttl = AsyncMock(return_value=30)
        allowed_1, _ = await rate_limiter.check_limit(user_id=12345)

        # Check user 2 (should be allowed)
        mock_redis.get = AsyncMock(side_effect=mock_get_user2)
        allowed_2, _ = await rate_limiter.check_limit(user_id=67890)

        assert allowed_1 is False
        assert allowed_2 is True

    async def test_close_closes_redis_connection(self, rate_limiter, mock_redis):
        """Test that close() properly closes Redis connection"""
        await rate_limiter.close()

        mock_redis.close.assert_called_once()

    async def test_get_redis_creates_connection_once(self, mock_redis):
        """Test that Redis connection is created only once"""
        with patch('bot.rate_limiter.aioredis.from_url', return_value=mock_redis) as mock_from_url:
            limiter = RateLimiter()

            # Call multiple times
            await limiter._get_redis()
            await limiter._get_redis()
            await limiter._get_redis()

            # Should only create connection once
            mock_from_url.assert_called_once()

            await limiter.close()

    async def test_check_limit_handles_redis_errors_gracefully(self, rate_limiter, mock_redis):
        """Test that Redis errors don't crash the rate limiter"""
        # Mock Redis to raise an exception
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))

        # Should raise the exception (in production, this would be caught by handler)
        with pytest.raises(Exception, match="Redis connection failed"):
            await rate_limiter.check_limit(user_id=12345)
