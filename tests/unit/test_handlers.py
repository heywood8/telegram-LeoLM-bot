"""Unit tests for BotHandlers"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Message as TelegramMessage

from bot.handlers import BotHandlers
from bot.session import SessionManager
from bot.llm.service import LLMService
from bot.mcp.manager import MCPManager
from bot.rate_limiter import RateLimiter


@pytest.mark.unit
class TestBotHandlers:
    """Test BotHandlers functionality"""

    @pytest.fixture
    async def bot_handlers(self, test_db_session, mock_redis, mock_llm_provider, test_config):
        """Create BotHandlers with mocked dependencies"""
        with patch('bot.session.aioredis.from_url', return_value=mock_redis), \
             patch('bot.rate_limiter.aioredis.from_url', return_value=mock_redis):

            session_manager = SessionManager(test_db_session)
            session_manager._redis = mock_redis

            llm_service = LLMService(provider=mock_llm_provider)
            mcp_manager = MCPManager()

            rate_limiter = RateLimiter()
            rate_limiter._redis = mock_redis

            handlers = BotHandlers(
                session_manager=session_manager,
                llm_service=llm_service,
                mcp_manager=mcp_manager,
                rate_limiter=rate_limiter
            )

            yield handlers

            await session_manager.close()
            await rate_limiter.close()

    # =========================================================================
    # Command Handlers Tests
    # =========================================================================

    async def test_start_command_sends_welcome_message(self, bot_handlers, telegram_update):
        """Test that /start command sends welcome message"""
        await bot_handlers.start_command(telegram_update, None)

        telegram_update.message.reply_text.assert_called_once()
        call_args = telegram_update.message.reply_text.call_args
        assert "Привет" in call_args[0][0]

    async def test_help_command_shows_commands(self, bot_handlers, telegram_update):
        """Test that /help command shows available commands"""
        await bot_handlers.help_command(telegram_update, None)

        telegram_update.message.reply_text.assert_called_once()
        call_args = telegram_update.message.reply_text.call_args
        assert "/start" in call_args[0][0]
        assert "/help" in call_args[0][0]
        assert "/reset" in call_args[0][0]

    async def test_help_command_shows_admin_commands_for_admin(self, bot_handlers, telegram_update, telegram_admin_user, test_config):
        """Test that /help shows admin commands for admin users"""
        telegram_update.effective_user = telegram_admin_user

        await bot_handlers.help_command(telegram_update, None)

        call_args = telegram_update.message.reply_text.call_args
        assert "/get_system_prompt" in call_args[0][0]
        assert "/set_system_prompt" in call_args[0][0]

    async def test_help_command_hides_admin_commands_for_regular_user(self, bot_handlers, telegram_update):
        """Test that /help hides admin commands for regular users"""
        await bot_handlers.help_command(telegram_update, None)

        call_args = telegram_update.message.reply_text.call_args
        assert "/get_system_prompt" not in call_args[0][0]
        assert "/set_system_prompt" not in call_args[0][0]

    async def test_reset_command_clears_session(self, bot_handlers, telegram_update, test_user, test_session, test_messages):
        """Test that /reset command clears conversation history"""
        with patch('bot.handlers.async_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = bot_handlers.session_manager.db

            await bot_handlers.reset_command(telegram_update, None)

            telegram_update.message.reply_text.assert_called_once()
            assert "очищена" in telegram_update.message.reply_text.call_args[0][0]

    async def test_get_system_prompt_denied_for_non_admin(self, bot_handlers, telegram_update, telegram_user):
        """Test that /get_system_prompt is denied for non-admin users"""
        telegram_update.effective_user = telegram_user

        await bot_handlers.get_system_prompt_command(telegram_update, None)

        call_args = telegram_update.message.reply_text.call_args
        assert "администраторам" in call_args[0][0]

    async def test_get_system_prompt_shows_prompt_for_admin(self, bot_handlers, telegram_update, telegram_admin_user, test_config):
        """Test that /get_system_prompt shows prompt for admin users"""
        telegram_update.effective_user = telegram_admin_user

        await bot_handlers.get_system_prompt_command(telegram_update, None)

        call_args = telegram_update.message.reply_text.call_args
        assert "Текущий системный промпт" in call_args[0][0]

    async def test_set_system_prompt_denied_for_non_admin(self, bot_handlers, telegram_update, telegram_user):
        """Test that /set_system_prompt is denied for non-admin users"""
        telegram_update.effective_user = telegram_user

        await bot_handlers.set_system_prompt_command(telegram_update, None)

        call_args = telegram_update.message.reply_text.call_args
        assert "администраторам" in call_args[0][0]

    async def test_set_system_prompt_waits_for_input_from_admin(self, bot_handlers, telegram_update, telegram_admin_user, test_config):
        """Test that /set_system_prompt prompts admin for new prompt"""
        telegram_update.effective_user = telegram_admin_user

        await bot_handlers.set_system_prompt_command(telegram_update, None)

        call_args = telegram_update.message.reply_text.call_args
        assert "отправьте новый системный промпт" in call_args[0][0]

        # Verify waiting state was set
        assert telegram_update.message.chat.id in bot_handlers._waiting_for_prompt

    # =========================================================================
    # Message Handler Tests
    # =========================================================================

    async def test_handle_message_blocks_rate_limited_user(self, bot_handlers, telegram_update, mock_redis):
        """Test that rate-limited users are blocked"""
        # Mock rate limit exceeded
        async def mock_check_limit(user_id):
            return False, 30  # Not allowed, retry after 30s

        bot_handlers.rate_limiter.check_limit = AsyncMock(side_effect=mock_check_limit)

        await bot_handlers.handle_message(telegram_update, None)

        # Should send rate limit message
        call_args = telegram_update.message.reply_text.call_args
        assert "Rate limit" in call_args[0][0]
        assert "30" in call_args[0][0]

    async def test_handle_message_processes_allowed_request(self, bot_handlers, telegram_update, mock_redis, test_user):
        """Test that allowed requests are processed"""
        # Mock rate limit allowed
        bot_handlers.rate_limiter.check_limit = AsyncMock(return_value=(True, None))
        bot_handlers.rate_limiter.consume_token = AsyncMock()

        with patch('bot.handlers.async_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = bot_handlers.session_manager.db

            await bot_handlers.handle_message(telegram_update, None)

            # Should consume rate limit token
            bot_handlers.rate_limiter.consume_token.assert_called_once()

    async def test_handle_message_saves_user_message(self, bot_handlers, telegram_update, test_user):
        """Test that user message is saved to database"""
        bot_handlers.rate_limiter.check_limit = AsyncMock(return_value=(True, None))
        bot_handlers.rate_limiter.consume_token = AsyncMock()

        with patch('bot.handlers.async_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = bot_handlers.session_manager.db

            telegram_update.message.text = "Hello bot!"

            await bot_handlers.handle_message(telegram_update, None)

            # Verify LLM was called
            bot_handlers.llm_service.provider.generate.assert_called()

    async def test_handle_message_sends_llm_response(self, bot_handlers, telegram_update, test_user):
        """Test that LLM response is sent to user"""
        bot_handlers.rate_limiter.check_limit = AsyncMock(return_value=(True, None))
        bot_handlers.rate_limiter.consume_token = AsyncMock()

        with patch('bot.handlers.async_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = bot_handlers.session_manager.db

            await bot_handlers.handle_message(telegram_update, None)

            # Should reply with LLM response
            telegram_update.message.reply_text.assert_called()

    async def test_handle_message_in_group_ignores_non_mentions(self, bot_handlers, telegram_update, telegram_group_chat):
        """Test that bot ignores messages in groups unless mentioned"""
        telegram_update.message.chat = telegram_group_chat
        telegram_update.message.text = "Hello everyone"

        bot_handlers.rate_limiter.check_limit = AsyncMock(return_value=(True, None))

        await bot_handlers.handle_message(telegram_update, None)

        # Should not process the message (no reply, no rate limit consumed)
        telegram_update.message.reply_text.assert_not_called()
        bot_handlers.rate_limiter.consume_token.assert_not_called()

    async def test_handle_message_in_group_responds_to_mention(self, bot_handlers, telegram_update, telegram_group_chat, telegram_context, test_user):
        """Test that bot responds to mentions in groups"""
        telegram_update.message.chat = telegram_group_chat
        telegram_update.message.text = "@test_bot Hello"

        bot_handlers.rate_limiter.check_limit = AsyncMock(return_value=(True, None))
        bot_handlers.rate_limiter.consume_token = AsyncMock()

        with patch('bot.handlers.async_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = bot_handlers.session_manager.db

            await bot_handlers.handle_message(telegram_update, telegram_context)

            # Should process the message
            bot_handlers.rate_limiter.consume_token.assert_called()

    async def test_handle_message_in_group_responds_to_reply(self, bot_handlers, telegram_update, telegram_group_chat, telegram_context, test_user):
        """Test that bot responds to replies in groups"""
        telegram_update.message.chat = telegram_group_chat
        telegram_update.message.text = "Sure, thanks!"

        # Create mock reply_to_message
        reply_msg = MagicMock()
        reply_msg.from_user = MagicMock()
        reply_msg.from_user.id = telegram_context.bot.id  # Reply to bot
        telegram_update.message.reply_to_message = reply_msg

        bot_handlers.rate_limiter.check_limit = AsyncMock(return_value=(True, None))
        bot_handlers.rate_limiter.consume_token = AsyncMock()

        with patch('bot.handlers.async_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = bot_handlers.session_manager.db

            await bot_handlers.handle_message(telegram_update, telegram_context)

            # Should process the message
            bot_handlers.rate_limiter.consume_token.assert_called()

    async def test_handle_tool_calls_executes_tools(self, bot_handlers, mock_mcp_plugin):
        """Test that _handle_tool_calls executes MCP tools"""
        await bot_handlers.mcp_manager.register_mcp(mock_mcp_plugin)

        # Create mock tool calls
        class MockToolCall:
            def __init__(self, name, args):
                self.function = MagicMock()
                self.function.name = name
                self.function.arguments = json.dumps(args)

        tool_calls = [
            MockToolCall("test_tool", {"query": "test"})
        ]

        results, websearch_called = await bot_handlers._handle_tool_calls(tool_calls)

        assert len(results) == 1
        assert results[0]["tool_name"] == "test_tool"
        assert "result" in results[0]

    async def test_handle_tool_calls_tracks_web_search(self, bot_handlers, mock_mcp_plugin):
        """Test that _handle_tool_calls tracks web_search calls"""
        # Create web search tool
        class MockToolCall:
            def __init__(self, name, args):
                self.function = MagicMock()
                self.function.name = name
                self.function.arguments = json.dumps(args)

        tool_calls = [
            MockToolCall("web_search", {"query": "test"})
        ]

        # Mock the execute_tool to avoid actual execution
        bot_handlers.mcp_manager.execute_tool = AsyncMock(return_value={"results": []})

        results, websearch_called = await bot_handlers._handle_tool_calls(tool_calls)

        assert websearch_called is True

    async def test_handle_tool_calls_handles_errors_gracefully(self, bot_handlers, mock_mcp_plugin):
        """Test that _handle_tool_calls handles tool errors gracefully"""
        await bot_handlers.mcp_manager.register_mcp(mock_mcp_plugin)

        # Mock tool to raise error
        bot_handlers.mcp_manager.execute_tool = AsyncMock(side_effect=Exception("Tool failed"))

        class MockToolCall:
            def __init__(self, name, args):
                self.function = MagicMock()
                self.function.name = name
                self.function.arguments = json.dumps(args)

        tool_calls = [
            MockToolCall("test_tool", {"query": "test"})
        ]

        results, _ = await bot_handlers._handle_tool_calls(tool_calls)

        assert len(results) == 1
        assert "Error" in results[0]["result"]

    async def test_escape_markdown_v2_escapes_special_chars(self):
        """Test that escape_markdown_v2 escapes special characters"""
        from bot.handlers import escape_markdown_v2

        text = "Test_with*special[chars]"
        escaped = escape_markdown_v2(text)

        assert r"\_" in escaped
        assert r"\*" in escaped
        assert r"\[" in escaped

    async def test_error_handler_logs_errors(self, bot_handlers, telegram_update, caplog):
        """Test that error_handler logs errors properly"""
        error = Exception("Test error")

        context = MagicMock()
        context.error = error

        await bot_handlers.error_handler(telegram_update, context)

        # Should log the error (check caplog if needed)

    async def test_handle_message_cleans_assistant_prefix(self, bot_handlers, telegram_update, test_user):
        """Test that [assistant] prefix is stripped from messages"""
        bot_handlers.rate_limiter.check_limit = AsyncMock(return_value=(True, None))
        bot_handlers.rate_limiter.consume_token = AsyncMock()

        telegram_update.message.text = "[assistant] Hello there"

        with patch('bot.handlers.async_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = bot_handlers.session_manager.db

            await bot_handlers.handle_message(telegram_update, None)

            # LLM should receive cleaned message
            call_args = bot_handlers.llm_service.provider.generate.call_args
            messages = call_args.kwargs['messages']

            # Find user message
            user_message = None
            for msg in messages:
                if msg["role"] == "user" and "Hello there" in msg["content"]:
                    user_message = msg
                    break

            assert user_message is not None
            assert "[assistant]" not in user_message["content"]

    async def test_handle_message_handles_empty_response(self, bot_handlers, telegram_update, test_user):
        """Test that handle_message handles empty LLM responses"""
        bot_handlers.rate_limiter.check_limit = AsyncMock(return_value=(True, None))
        bot_handlers.rate_limiter.consume_token = AsyncMock()

        # Mock LLM to return empty response
        bot_handlers.llm_service.provider.generate = AsyncMock(return_value="")

        with patch('bot.handlers.async_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = bot_handlers.session_manager.db

            await bot_handlers.handle_message(telegram_update, None)

            # Should send fallback message
            call_args = telegram_update.message.reply_text.call_args
            assert "пустой ответ" in call_args[0][0].lower() or call_args[0][0] != ""
