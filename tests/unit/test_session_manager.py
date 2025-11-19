"""Unit tests for SessionManager"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from bot.session import SessionManager, UserSession, Message
from bot.models import User, Session as SessionModel, Message as MessageModel


@pytest.mark.unit
class TestSessionManager:
    """Test SessionManager functionality"""

    @pytest.fixture
    async def session_manager(self, test_db_session, mock_redis):
        """Create session manager with test database and mocked Redis"""
        with patch('bot.session.aioredis.from_url', return_value=mock_redis):
            manager = SessionManager(test_db_session)
            manager._redis = mock_redis
            yield manager
            await manager.close()

    async def test_get_session_creates_new_user(self, session_manager, telegram_user, mock_redis):
        """Test that get_session creates a new user if doesn't exist"""
        # Mock Redis to return no cache
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)

        user_session = await session_manager.get_session(
            user_id=12345,
            telegram_id=12345,
            telegram_user=telegram_user
        )

        assert user_session is not None
        assert user_session.user_id > 0
        assert user_session.session_id > 0

    async def test_get_session_uses_existing_user(self, session_manager, test_user, telegram_user, mock_redis):
        """Test that get_session uses existing user"""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)

        user_session = await session_manager.get_session(
            user_id=test_user.telegram_id,
            telegram_id=test_user.telegram_id,
            telegram_user=telegram_user
        )

        assert user_session.user_id == test_user.id

    async def test_get_session_returns_cached_session(self, session_manager, test_user, test_session, mock_redis):
        """Test that get_session returns cached session if available"""
        # Mock cached session data
        cached_data = {
            "user_id": test_user.id,
            "session_id": test_session.id,
            "created_at": test_session.created_at.isoformat(),
            "last_active": test_session.last_active.isoformat(),
            "active_mcps": [],
            "preferences": {},
            "metadata": {}
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        user_session = await session_manager.get_session(
            user_id=test_user.telegram_id,
            telegram_id=test_user.telegram_id
        )

        assert user_session.session_id == test_session.id
        mock_redis.get.assert_called_once_with(f"session:{test_user.telegram_id}")

    async def test_update_context_adds_message(self, session_manager, test_session):
        """Test that update_context adds a message to the session"""
        await session_manager.update_context(
            session_id=test_session.id,
            role="user",
            content="Test message",
            tokens=10,
            metadata={"test": "data"}
        )

        # Verify message was added to database
        stmt = select(MessageModel).where(MessageModel.session_id == test_session.id)
        result = await session_manager.db.execute(stmt)
        messages = result.scalars().all()

        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "Test message"
        assert messages[0].tokens == 10
        assert messages[0].message_metadata == {"test": "data"}

    async def test_get_context_window_returns_recent_messages(self, session_manager, test_session, test_messages):
        """Test that get_context_window returns recent messages"""
        context = await session_manager.get_context_window(test_session.id)

        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "Hello"
        assert context[1]["role"] == "assistant"
        assert context[1]["content"] == "Hi there!"

    async def test_get_context_window_respects_token_limit(self, session_manager, test_session, test_db_session):
        """Test that get_context_window respects max token limit"""
        # Add many messages
        for i in range(20):
            msg = MessageModel(
                session_id=test_session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                tokens=100,
                message_metadata={}
            )
            test_db_session.add(msg)
        await test_db_session.commit()

        # Get context with small token limit
        context = await session_manager.get_context_window(
            test_session.id,
            max_tokens=500  # Should only fit ~5 messages
        )

        # Should return fewer messages due to token limit
        assert len(context) <= 5

    async def test_clear_session_deletes_messages(self, session_manager, test_session, test_messages):
        """Test that clear_session deletes all messages"""
        # Verify messages exist
        stmt = select(MessageModel).where(MessageModel.session_id == test_session.id)
        result = await session_manager.db.execute(stmt)
        messages_before = result.scalars().all()
        assert len(messages_before) == 2

        # Clear session
        await session_manager.clear_session(test_session.id)
        await session_manager.db.commit()

        # Verify messages are deleted
        result = await session_manager.db.execute(stmt)
        messages_after = result.scalars().all()
        assert len(messages_after) == 0

    async def test_load_messages_returns_limited_count(self, session_manager, test_session, test_db_session):
        """Test that _load_messages returns limited number of messages"""
        # Add 20 messages
        for i in range(20):
            msg = MessageModel(
                session_id=test_session.id,
                role="user",
                content=f"Message {i}",
                message_metadata={}
            )
            test_db_session.add(msg)
        await test_db_session.commit()

        # Load with default limit (10)
        messages = await session_manager._load_messages(test_session.id, limit=10)

        assert len(messages) == 10

    async def test_load_messages_returns_chronological_order(self, session_manager, test_session, test_messages):
        """Test that _load_messages returns messages in chronological order"""
        messages = await session_manager._load_messages(test_session.id)

        # First message should be the oldest (user message)
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"

        # Last message should be the newest (assistant message)
        assert messages[-1].role == "assistant"
        assert messages[-1].content == "Hi there!"

    async def test_get_or_create_user_creates_admin_user(self, session_manager, telegram_admin_user, test_config):
        """Test that _get_or_create_user marks admin users correctly"""
        user = await session_manager._get_or_create_user(
            telegram_id=99999,
            telegram_user=telegram_admin_user
        )

        assert user.is_admin is True
        assert user.telegram_id == 99999

    async def test_get_or_create_user_updates_changed_info(self, session_manager, test_user, telegram_user):
        """Test that _get_or_create_user updates user info if changed"""
        # Change username
        telegram_user.username = "new_username"
        telegram_user.first_name = "New"

        user = await session_manager._get_or_create_user(
            telegram_id=test_user.telegram_id,
            telegram_user=telegram_user
        )
        await session_manager.db.commit()
        await session_manager.db.refresh(user)

        assert user.username == "new_username"
        assert user.first_name == "New"

    async def test_serialize_session_converts_to_dict(self, session_manager, test_user, test_session):
        """Test that _serialize_session converts UserSession to dict"""
        user_session = UserSession(
            user_id=test_user.id,
            session_id=test_session.id,
            created_at=test_session.created_at,
            last_active=test_session.last_active,
            active_mcps=["test_mcp"],
            preferences={"lang": "en"},
            metadata={"key": "value"}
        )

        serialized = session_manager._serialize_session(user_session)

        assert serialized["user_id"] == test_user.id
        assert serialized["session_id"] == test_session.id
        assert serialized["active_mcps"] == ["test_mcp"]
        assert serialized["preferences"] == {"lang": "en"}
        assert serialized["metadata"] == {"key": "value"}
        assert isinstance(serialized["created_at"], str)
        assert isinstance(serialized["last_active"], str)

    async def test_close_closes_redis_connection(self, session_manager, mock_redis):
        """Test that close() closes Redis connection"""
        await session_manager.close()

        mock_redis.close.assert_called_once()

    async def test_update_context_updates_session_last_active(self, session_manager, test_session, test_db_session):
        """Test that update_context updates session last_active timestamp"""
        original_last_active = test_session.last_active

        # Wait a moment and add a message
        await session_manager.update_context(
            session_id=test_session.id,
            role="user",
            content="New message"
        )
        await test_db_session.commit()

        # Refresh session from database
        await test_db_session.refresh(test_session)

        # last_active should be updated
        assert test_session.last_active >= original_last_active

    async def test_get_context_window_with_no_messages(self, session_manager, test_session):
        """Test that get_context_window returns empty list when no messages"""
        context = await session_manager.get_context_window(test_session.id)

        assert context == []

    async def test_get_session_creates_new_session_if_none_exists(self, session_manager, test_user, telegram_user, mock_redis, test_db_session):
        """Test that get_session creates a new session if user has none"""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)

        # Delete any existing sessions for this user
        from sqlalchemy import delete
        await test_db_session.execute(delete(SessionModel).where(SessionModel.user_id == test_user.id))
        await test_db_session.commit()

        user_session = await session_manager.get_session(
            user_id=test_user.telegram_id,
            telegram_id=test_user.telegram_id,
            telegram_user=telegram_user
        )

        assert user_session is not None
        assert user_session.session_id > 0
