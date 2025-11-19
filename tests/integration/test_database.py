"""Integration tests for database operations"""

import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import User, Session as SessionModel, Message, SystemPrompt


@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database models and relationships"""

    async def test_create_user(self, test_db_session: AsyncSession):
        """Test creating a user in the database"""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            last_name="User",
            is_admin=False,
            is_blocked=False,
            preferences={"lang": "en"}
        )

        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        assert user.id is not None
        assert user.telegram_id == 123456
        assert user.username == "testuser"
        assert user.preferences == {"lang": "en"}

    async def test_create_session_for_user(self, test_db_session: AsyncSession, test_user: User):
        """Test creating a session for a user"""
        session = SessionModel(
            user_id=test_user.id,
            active_mcps=["web", "news"],
            session_metadata={"test": "data"}
        )

        test_db_session.add(session)
        await test_db_session.commit()
        await test_db_session.refresh(session)

        assert session.id is not None
        assert session.user_id == test_user.id
        assert session.active_mcps == ["web", "news"]
        assert session.created_at is not None
        assert session.last_active is not None

    async def test_user_session_relationship(self, test_db_session: AsyncSession, test_user: User):
        """Test User -> Sessions relationship"""
        # Create multiple sessions for user
        session1 = SessionModel(user_id=test_user.id, active_mcps=[])
        session2 = SessionModel(user_id=test_user.id, active_mcps=[])

        test_db_session.add_all([session1, session2])
        await test_db_session.commit()

        # Query user with sessions
        stmt = select(User).where(User.id == test_user.id)
        result = await test_db_session.execute(stmt)
        user = result.scalar_one()

        # Verify relationship
        assert len(user.sessions) == 2

    async def test_create_message_in_session(self, test_db_session: AsyncSession, test_session: SessionModel):
        """Test creating messages in a session"""
        message = Message(
            session_id=test_session.id,
            role="user",
            content="Hello, bot!",
            tokens=10,
            message_metadata={"source": "telegram"}
        )

        test_db_session.add(message)
        await test_db_session.commit()
        await test_db_session.refresh(message)

        assert message.id is not None
        assert message.session_id == test_session.id
        assert message.role == "user"
        assert message.content == "Hello, bot!"
        assert message.tokens == 10

    async def test_session_messages_relationship(self, test_db_session: AsyncSession, test_session: SessionModel):
        """Test Session -> Messages relationship"""
        # Create multiple messages
        messages = [
            Message(session_id=test_session.id, role="user", content="Hi"),
            Message(session_id=test_session.id, role="assistant", content="Hello"),
            Message(session_id=test_session.id, role="user", content="How are you?"),
        ]

        test_db_session.add_all(messages)
        await test_db_session.commit()

        # Query session with messages
        stmt = select(SessionModel).where(SessionModel.id == test_session.id)
        result = await test_db_session.execute(stmt)
        session = result.scalar_one()

        # Verify relationship
        assert len(session.messages) == 3

    async def test_create_system_prompt(self, test_db_session: AsyncSession, test_admin_user: User):
        """Test creating a system prompt"""
        prompt = SystemPrompt(
            prompt="You are a helpful assistant",
            set_by_user_id=test_admin_user.id,
            is_active=True
        )

        test_db_session.add(prompt)
        await test_db_session.commit()
        await test_db_session.refresh(prompt)

        assert prompt.id is not None
        assert prompt.prompt == "You are a helpful assistant"
        assert prompt.set_by_user_id == test_admin_user.id
        assert prompt.is_active is True

    async def test_only_one_active_system_prompt(self, test_db_session: AsyncSession, test_admin_user: User):
        """Test that only one system prompt can be active at a time"""
        # Create first prompt
        prompt1 = SystemPrompt(
            prompt="First prompt",
            set_by_user_id=test_admin_user.id,
            is_active=True
        )
        test_db_session.add(prompt1)
        await test_db_session.commit()

        # Create second prompt and deactivate first
        from sqlalchemy import update
        await test_db_session.execute(
            update(SystemPrompt)
            .where(SystemPrompt.is_active == True)
            .values(is_active=False)
        )

        prompt2 = SystemPrompt(
            prompt="Second prompt",
            set_by_user_id=test_admin_user.id,
            is_active=True
        )
        test_db_session.add(prompt2)
        await test_db_session.commit()

        # Query active prompts
        stmt = select(SystemPrompt).where(SystemPrompt.is_active == True)
        result = await test_db_session.execute(stmt)
        active_prompts = result.scalars().all()

        assert len(active_prompts) == 1
        assert active_prompts[0].prompt == "Second prompt"

    async def test_message_ordering_by_created_at(self, test_db_session: AsyncSession, test_session: SessionModel):
        """Test that messages are ordered by created_at"""
        # Create messages
        msg1 = Message(session_id=test_session.id, role="user", content="First")
        test_db_session.add(msg1)
        await test_db_session.commit()

        msg2 = Message(session_id=test_session.id, role="assistant", content="Second")
        test_db_session.add(msg2)
        await test_db_session.commit()

        msg3 = Message(session_id=test_session.id, role="user", content="Third")
        test_db_session.add(msg3)
        await test_db_session.commit()

        # Query messages ordered by created_at
        stmt = select(Message).where(Message.session_id == test_session.id).order_by(Message.created_at)
        result = await test_db_session.execute(stmt)
        messages = result.scalars().all()

        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
        assert messages[2].content == "Third"

    async def test_cascade_delete_session_deletes_messages(self, test_db_session: AsyncSession, test_user: User):
        """Test that deleting a session cascades to delete messages"""
        # Create session with messages
        session = SessionModel(user_id=test_user.id, active_mcps=[])
        test_db_session.add(session)
        await test_db_session.commit()

        msg1 = Message(session_id=session.id, role="user", content="Test")
        msg2 = Message(session_id=session.id, role="assistant", content="Response")
        test_db_session.add_all([msg1, msg2])
        await test_db_session.commit()

        session_id = session.id

        # Delete session
        await test_db_session.delete(session)
        await test_db_session.commit()

        # Verify messages are deleted
        stmt = select(Message).where(Message.session_id == session_id)
        result = await test_db_session.execute(stmt)
        messages = result.scalars().all()

        assert len(messages) == 0

    async def test_user_unique_telegram_id(self, test_db_session: AsyncSession):
        """Test that telegram_id must be unique"""
        user1 = User(telegram_id=999, username="user1", is_admin=False, is_blocked=False)
        test_db_session.add(user1)
        await test_db_session.commit()

        # Try to create another user with same telegram_id
        user2 = User(telegram_id=999, username="user2", is_admin=False, is_blocked=False)
        test_db_session.add(user2)

        with pytest.raises(Exception):  # Should raise integrity error
            await test_db_session.commit()

    async def test_user_preferences_json_storage(self, test_db_session: AsyncSession):
        """Test that user preferences are stored as JSON"""
        user = User(
            telegram_id=888,
            username="jsonuser",
            is_admin=False,
            is_blocked=False,
            preferences={
                "language": "ru",
                "notifications": True,
                "theme": "dark",
                "nested": {"key": "value"}
            }
        )

        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        assert user.preferences["language"] == "ru"
        assert user.preferences["notifications"] is True
        assert user.preferences["nested"]["key"] == "value"

    async def test_session_metadata_json_storage(self, test_db_session: AsyncSession, test_user: User):
        """Test that session metadata is stored as JSON"""
        session = SessionModel(
            user_id=test_user.id,
            active_mcps=["web"],
            session_metadata={
                "start_time": "2024-01-01T00:00:00",
                "context": {"key": "value"},
                "flags": [1, 2, 3]
            }
        )

        test_db_session.add(session)
        await test_db_session.commit()
        await test_db_session.refresh(session)

        assert session.session_metadata["start_time"] == "2024-01-01T00:00:00"
        assert session.session_metadata["context"]["key"] == "value"
        assert session.session_metadata["flags"] == [1, 2, 3]

    async def test_message_metadata_json_storage(self, test_db_session: AsyncSession, test_session: SessionModel):
        """Test that message metadata is stored as JSON"""
        message = Message(
            session_id=test_session.id,
            role="assistant",
            content="Test response",
            message_metadata={
                "tool_called": True,
                "tools": ["web_search", "news"],
                "response_time": 1.5
            }
        )

        test_db_session.add(message)
        await test_db_session.commit()
        await test_db_session.refresh(message)

        assert message.message_metadata["tool_called"] is True
        assert message.message_metadata["tools"] == ["web_search", "news"]
        assert message.message_metadata["response_time"] == 1.5

    async def test_query_recent_active_sessions(self, test_db_session: AsyncSession, test_user: User):
        """Test querying sessions by last_active timestamp"""
        # Create sessions with different last_active times
        from datetime import datetime, timedelta

        old_session = SessionModel(
            user_id=test_user.id,
            active_mcps=[],
            last_active=datetime.utcnow() - timedelta(days=7)
        )

        recent_session = SessionModel(
            user_id=test_user.id,
            active_mcps=[],
            last_active=datetime.utcnow()
        )

        test_db_session.add_all([old_session, recent_session])
        await test_db_session.commit()

        # Query sessions from last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        stmt = select(SessionModel).where(
            SessionModel.user_id == test_user.id,
            SessionModel.last_active > cutoff
        )
        result = await test_db_session.execute(stmt)
        recent_sessions = result.scalars().all()

        assert len(recent_sessions) == 1
        assert recent_sessions[0].id == recent_session.id

    async def test_count_messages_by_role(self, test_db_session: AsyncSession, test_session: SessionModel):
        """Test counting messages by role"""
        from sqlalchemy import func

        # Create messages with different roles
        messages = [
            Message(session_id=test_session.id, role="user", content="1"),
            Message(session_id=test_session.id, role="user", content="2"),
            Message(session_id=test_session.id, role="assistant", content="3"),
            Message(session_id=test_session.id, role="system", content="4"),
        ]

        test_db_session.add_all(messages)
        await test_db_session.commit()

        # Count user messages
        stmt = select(func.count(Message.id)).where(
            Message.session_id == test_session.id,
            Message.role == "user"
        )
        result = await test_db_session.execute(stmt)
        user_count = result.scalar()

        assert user_count == 2
