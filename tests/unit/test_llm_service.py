"""Unit tests for LLMService"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from bot.llm.service import LLMService
from bot.llm.base import BaseLLMProvider


@pytest.mark.unit
class TestLLMService:
    """Test LLMService functionality"""

    @pytest.fixture
    def llm_service(self, mock_llm_provider):
        """Create LLM service with mocked provider"""
        return LLMService(provider=mock_llm_provider)

    async def test_process_message_calls_provider_generate(self, llm_service, mock_llm_provider):
        """Test that process_message calls provider.generate()"""
        context = [
            {"role": "user", "content": "Hello"}
        ]

        response = await llm_service.process_message(
            user_message="How are you?",
            context=context
        )

        mock_llm_provider.generate.assert_called_once()
        assert response == "This is a test response from the LLM"

    async def test_process_message_includes_system_prompt(self, llm_service, mock_llm_provider):
        """Test that process_message includes system prompt"""
        context = []

        await llm_service.process_message(
            user_message="Test",
            context=context
        )

        # Verify system prompt was added
        call_args = mock_llm_provider.generate.call_args
        messages = call_args.kwargs['messages']

        assert messages[0]["role"] == "system"
        assert "Лео" in messages[0]["content"]

    async def test_process_message_includes_tools_in_system_prompt(self, llm_service, mock_llm_provider):
        """Test that system prompt mentions tools when available"""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool"
                }
            }
        ]

        await llm_service.process_message(
            user_message="Test",
            context=[],
            tools=tools
        )

        # Verify system prompt mentions tools
        call_args = mock_llm_provider.generate.call_args
        messages = call_args.kwargs['messages']

        assert "инструмент" in messages[0]["content"].lower()

    async def test_process_message_adds_context_messages(self, llm_service, mock_llm_provider):
        """Test that process_message includes conversation context"""
        context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        await llm_service.process_message(
            user_message="How are you?",
            context=context
        )

        call_args = mock_llm_provider.generate.call_args
        messages = call_args.kwargs['messages']

        # Should have: system + 2 context + user message
        assert len(messages) == 4
        assert messages[1] == context[0]
        assert messages[2] == context[1]

    async def test_process_message_adds_mcp_context(self, llm_service, mock_llm_provider):
        """Test that process_message injects MCP context"""
        mcp_context = {
            "test_mcp": {"data": "test data"}
        }

        await llm_service.process_message(
            user_message="Test",
            context=[],
            mcp_context=mcp_context
        )

        call_args = mock_llm_provider.generate.call_args
        messages = call_args.kwargs['messages']

        # Find the MCP context message
        mcp_message = None
        for msg in messages:
            if msg["role"] == "system" and "Additional context" in msg["content"]:
                mcp_message = msg
                break

        assert mcp_message is not None
        assert "test_mcp" in mcp_message["content"]

    async def test_process_message_adds_user_message_last(self, llm_service, mock_llm_provider):
        """Test that user message is added last"""
        context = [
            {"role": "user", "content": "Hello"}
        ]

        await llm_service.process_message(
            user_message="How are you?",
            context=context
        )

        call_args = mock_llm_provider.generate.call_args
        messages = call_args.kwargs['messages']

        # Last message should be the current user message
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "How are you?"

    async def test_process_message_passes_tools_to_provider(self, llm_service, mock_llm_provider):
        """Test that tools are passed to provider"""
        tools = [
            {
                "type": "function",
                "function": {"name": "test_tool"}
            }
        ]

        await llm_service.process_message(
            user_message="Test",
            context=[],
            tools=tools
        )

        call_args = mock_llm_provider.generate.call_args
        assert call_args.kwargs['tools'] == tools

    async def test_process_message_passes_stream_parameter(self, llm_service, mock_llm_provider):
        """Test that stream parameter is passed to provider"""
        await llm_service.process_message(
            user_message="Test",
            context=[],
            stream=True
        )

        call_args = mock_llm_provider.generate.call_args
        assert call_args.kwargs['stream'] is True

    async def test_format_mcp_context_formats_correctly(self, llm_service):
        """Test that _format_mcp_context formats data correctly"""
        mcp_context = {
            "mcp1": {"key": "value"},
            "mcp2": {"data": "test"}
        }

        formatted = llm_service._format_mcp_context(mcp_context)

        assert "[mcp1]" in formatted
        assert "[mcp2]" in formatted
        assert '"key": "value"' in formatted
        assert '"data": "test"' in formatted

    async def test_health_check_calls_provider_health_check(self, llm_service, mock_llm_provider):
        """Test that health_check calls provider's health_check"""
        mock_llm_provider.health_check = AsyncMock(return_value=True)

        result = await llm_service.health_check()

        mock_llm_provider.health_check.assert_called_once()
        assert result is True

    async def test_health_check_returns_false_on_failure(self, llm_service, mock_llm_provider):
        """Test that health_check returns False when provider fails"""
        mock_llm_provider.health_check = AsyncMock(return_value=False)

        result = await llm_service.health_check()

        assert result is False

    def test_system_prompt_property_returns_prompt(self, llm_service):
        """Test that system_prompt property returns the prompt"""
        prompt = llm_service.system_prompt

        assert prompt is not None
        assert isinstance(prompt, str)
        assert "Лео" in prompt

    def test_update_system_prompt_changes_prompt(self, llm_service):
        """Test that update_system_prompt updates the custom prompt"""
        new_prompt = "This is a custom system prompt"

        llm_service.update_system_prompt(new_prompt)

        assert llm_service.custom_system_prompt == new_prompt
        assert llm_service.system_prompt == new_prompt

    async def test_process_message_uses_custom_system_prompt(self, llm_service, mock_llm_provider):
        """Test that custom system prompt is used when set"""
        custom_prompt = "Custom prompt text"
        llm_service.update_system_prompt(custom_prompt)

        await llm_service.process_message(
            user_message="Test",
            context=[]
        )

        call_args = mock_llm_provider.generate.call_args
        messages = call_args.kwargs['messages']

        # System prompt should use custom text
        assert messages[0]["role"] == "system"
        assert custom_prompt in messages[0]["content"]

    async def test_load_system_prompt_with_tools(self, llm_service):
        """Test that _load_system_prompt includes tool instructions when has_tools=True"""
        prompt_with_tools = llm_service._load_system_prompt(has_tools=True)
        prompt_without_tools = llm_service._load_system_prompt(has_tools=False)

        assert "инструмент" in prompt_with_tools.lower()
        assert len(prompt_with_tools) > len(prompt_without_tools)

    async def test_process_message_with_empty_context(self, llm_service, mock_llm_provider):
        """Test that process_message works with empty context"""
        response = await llm_service.process_message(
            user_message="Test",
            context=[]
        )

        assert response is not None
        mock_llm_provider.generate.assert_called_once()

    async def test_process_message_passes_temperature_and_max_tokens(self, llm_service, mock_llm_provider, test_config):
        """Test that temperature and max_tokens from config are passed"""
        await llm_service.process_message(
            user_message="Test",
            context=[]
        )

        call_args = mock_llm_provider.generate.call_args

        assert 'temperature' in call_args.kwargs
        assert 'max_tokens' in call_args.kwargs
