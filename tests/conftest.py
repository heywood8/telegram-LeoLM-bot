"""Shared pytest fixtures for all tests"""

import os
import pytest
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import redis.asyncio as aioredis
from telegram import Update, Message, User as TelegramUser, Chat
from telegram.ext import ContextTypes

# Set required environment variables before importing config
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test_token_123456789')
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///:memory:')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('SECRET_KEY', 'test_secret_key_for_testing_only')
os.environ.setdefault('ADMIN_USER_IDS', '99999')

from bot.models import Base, User, Session as SessionModel, Message as MessageModel
from bot.config import config
from bot.llm.base import BaseLLMProvider
from bot.mcp.base import BaseMCP


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db_engine():
    """Create test database engine (in-memory SQLite)"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def test_user(test_db_session: AsyncSession) -> User:
    """Create test user in database"""
    user = User(
        telegram_id=12345,
        username="test_user",
        first_name="Test",
        last_name="User",
        is_admin=False,
        is_blocked=False,
        preferences={}
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
async def test_admin_user(test_db_session: AsyncSession) -> User:
    """Create test admin user in database"""
    user = User(
        telegram_id=99999,
        username="admin_user",
        first_name="Admin",
        last_name="User",
        is_admin=True,
        is_blocked=False,
        preferences={}
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
async def test_session(test_db_session: AsyncSession, test_user: User) -> SessionModel:
    """Create test session in database"""
    session = SessionModel(
        user_id=test_user.id,
        active_mcps=[],
        session_metadata={}
    )
    test_db_session.add(session)
    await test_db_session.commit()
    await test_db_session.refresh(session)
    return session


@pytest.fixture(scope="function")
async def test_messages(test_db_session: AsyncSession, test_session: SessionModel):
    """Create test messages in database"""
    messages = [
        MessageModel(
            session_id=test_session.id,
            role="user",
            content="Hello",
            tokens=5,
            message_metadata={}
        ),
        MessageModel(
            session_id=test_session.id,
            role="assistant",
            content="Hi there!",
            tokens=8,
            message_metadata={}
        ),
    ]
    test_db_session.add_all(messages)
    await test_db_session.commit()
    return messages


# ============================================================================
# Redis Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def mock_redis():
    """Create mock Redis client"""
    redis_mock = AsyncMock(spec=aioredis.Redis)

    # Setup mock data store
    _data = {}
    _expires = {}

    async def mock_get(key):
        if key in _expires and datetime.utcnow().timestamp() > _expires[key]:
            del _data[key]
            del _expires[key]
            return None
        return _data.get(key)

    async def mock_set(key, value):
        _data[key] = value
        return True

    async def mock_setex(key, ttl, value):
        _data[key] = value
        _expires[key] = datetime.utcnow().timestamp() + ttl
        return True

    async def mock_incr(key):
        _data[key] = _data.get(key, 0) + 1
        return _data[key]

    async def mock_expire(key, ttl):
        _expires[key] = datetime.utcnow().timestamp() + ttl
        return True

    async def mock_ttl(key):
        if key in _expires:
            remaining = _expires[key] - datetime.utcnow().timestamp()
            return int(max(0, remaining))
        return -1

    async def mock_delete(key):
        if key in _data:
            del _data[key]
        if key in _expires:
            del _expires[key]
        return 1

    def mock_pipeline():
        pipe = MagicMock()
        pipe.incr = MagicMock(side_effect=lambda k: None)
        pipe.expire = MagicMock(side_effect=lambda k, t: None)

        async def execute_mock():
            return [1, True, 1, True]

        pipe.execute = AsyncMock(side_effect=execute_mock)
        return pipe

    redis_mock.get = AsyncMock(side_effect=mock_get)
    redis_mock.set = AsyncMock(side_effect=mock_set)
    redis_mock.setex = AsyncMock(side_effect=mock_setex)
    redis_mock.incr = AsyncMock(side_effect=mock_incr)
    redis_mock.expire = AsyncMock(side_effect=mock_expire)
    redis_mock.ttl = AsyncMock(side_effect=mock_ttl)
    redis_mock.delete = AsyncMock(side_effect=mock_delete)
    redis_mock.pipeline = MagicMock(side_effect=mock_pipeline)
    redis_mock.close = AsyncMock()

    return redis_mock


# ============================================================================
# Telegram Fixtures
# ============================================================================

@pytest.fixture
def telegram_user():
    """Create mock Telegram user"""
    user = MagicMock(spec=TelegramUser)
    user.id = 12345
    user.username = "test_user"
    user.first_name = "Test"
    user.last_name = "User"
    user.is_bot = False
    return user


@pytest.fixture
def telegram_admin_user():
    """Create mock Telegram admin user"""
    user = MagicMock(spec=TelegramUser)
    user.id = 99999
    user.username = "admin_user"
    user.first_name = "Admin"
    user.last_name = "User"
    user.is_bot = False
    return user


@pytest.fixture
def telegram_chat():
    """Create mock Telegram chat (private)"""
    chat = MagicMock(spec=Chat)
    chat.id = 12345
    chat.type = "private"
    chat.username = "test_user"
    return chat


@pytest.fixture
def telegram_group_chat():
    """Create mock Telegram group chat"""
    chat = MagicMock(spec=Chat)
    chat.id = -100123456789
    chat.type = "supergroup"
    chat.title = "Test Group"
    return chat


@pytest.fixture
def telegram_message(telegram_user, telegram_chat):
    """Create mock Telegram message"""
    message = MagicMock(spec=Message)
    message.message_id = 1
    message.from_user = telegram_user
    message.chat = telegram_chat
    message.text = "Test message"
    message.entities = []
    message.reply_to_message = None
    message.reply_text = AsyncMock()
    message.date = datetime.utcnow()
    return message


@pytest.fixture
def telegram_update(telegram_message, telegram_user):
    """Create mock Telegram update"""
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.message = telegram_message
    update.effective_user = telegram_user
    update.effective_chat = telegram_message.chat
    return update


@pytest.fixture
def telegram_context():
    """Create mock Telegram context"""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    # Mock bot
    bot = MagicMock()
    bot.id = 987654321
    bot.username = "test_bot"
    bot.first_name = "TestBot"
    bot.send_message = AsyncMock()

    context.bot = bot
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}

    return context


# ============================================================================
# LLM Provider Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_provider():
    """Create mock LLM provider"""
    provider = AsyncMock(spec=BaseLLMProvider)

    # Mock simple text response
    async def mock_generate(messages, **kwargs):
        return "This is a test response from the LLM"

    # Mock tool call response
    class MockToolCall:
        def __init__(self, name, args):
            self.function = MagicMock()
            self.function.name = name
            self.function.arguments = args

    class MockResponseWithTools:
        def __init__(self):
            self.content = ""
            self.tool_calls = [
                MockToolCall("web_search", '{"query": "test query"}')
            ]

    provider.generate = AsyncMock(side_effect=mock_generate)
    provider.health_check = AsyncMock(return_value=True)

    return provider


@pytest.fixture
def mock_llm_provider_with_tools():
    """Create mock LLM provider that returns tool calls"""
    provider = AsyncMock(spec=BaseLLMProvider)

    class MockToolCall:
        def __init__(self, name, args):
            self.function = MagicMock()
            self.function.name = name
            self.function.arguments = args

    class MockResponse:
        def __init__(self, with_tools=True):
            if with_tools:
                self.content = ""
                self.tool_calls = [
                    MockToolCall("web_search", '{"query": "test"}')
                ]
            else:
                self.content = "Final synthesized response"
                self.tool_calls = None

    call_count = 0

    async def mock_generate(messages, tools=None, **kwargs):
        nonlocal call_count
        call_count += 1

        # First call: return tool calls
        if call_count == 1 and tools:
            return MockResponse(with_tools=True)
        # Second call: return final response
        else:
            return MockResponse(with_tools=False)

    provider.generate = AsyncMock(side_effect=mock_generate)
    provider.health_check = AsyncMock(return_value=True)

    return provider


# ============================================================================
# MCP Fixtures
# ============================================================================

@pytest.fixture
def mock_mcp_plugin():
    """Create mock MCP plugin"""
    mcp = AsyncMock(spec=BaseMCP)
    mcp.name = "test_mcp"
    mcp.enabled = True
    mcp.metadata = {
        "name": "test_mcp",
        "description": "Test MCP plugin",
        "version": "1.0.0"
    }

    async def mock_get_tools():
        return [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        }
                    }
                }
            }
        ]

    async def mock_execute_tool(tool_name, parameters):
        if tool_name == "test_tool":
            return {"result": f"Executed {tool_name} with {parameters}"}
        raise ValueError(f"Unknown tool: {tool_name}")

    async def mock_get_context(query):
        return {"context": f"Context for {query}"}

    mcp.initialize = AsyncMock()
    mcp.get_tools = AsyncMock(side_effect=mock_get_tools)
    mcp.execute_tool = AsyncMock(side_effect=mock_execute_tool)
    mcp.get_context = AsyncMock(side_effect=mock_get_context)
    mcp.shutdown = AsyncMock()

    return mcp


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def test_config(monkeypatch):
    """Override config for testing"""
    # Mock admin IDs
    monkeypatch.setattr(config.security, 'admin_ids', [99999])

    # Mock rate limits (more lenient for tests)
    monkeypatch.setattr(config.rate_limit, 'user_requests', 100)
    monkeypatch.setattr(config.rate_limit, 'user_window', 60)

    return config


# ============================================================================
# Utility Functions
# ============================================================================

def assert_log_contains(caplog, level: str, message: str):
    """Assert that a log message was recorded"""
    for record in caplog.records:
        if record.levelname == level and message in record.message:
            return True
    raise AssertionError(f"Log message not found: [{level}] {message}")


@pytest.fixture
def assert_logs():
    """Provide log assertion helper"""
    return assert_log_contains
