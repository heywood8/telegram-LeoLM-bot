"""Unit tests for MCPManager"""

import pytest
from unittest.mock import AsyncMock

from bot.mcp.manager import MCPManager
from bot.mcp.base import BaseMCP


@pytest.mark.unit
class TestMCPManager:
    """Test MCPManager functionality"""

    @pytest.fixture
    def mcp_manager(self):
        """Create MCP manager"""
        return MCPManager()

    async def test_register_mcp_adds_plugin(self, mcp_manager, mock_mcp_plugin):
        """Test that register_mcp adds a plugin to the manager"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        assert "test_mcp" in mcp_manager.mcps
        assert mcp_manager.mcps["test_mcp"] == mock_mcp_plugin
        mock_mcp_plugin.initialize.assert_called_once()

    async def test_register_mcp_registers_tools(self, mcp_manager, mock_mcp_plugin):
        """Test that register_mcp registers all tools from the plugin"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        assert "test_tool" in mcp_manager.tool_registry
        assert mcp_manager.tool_registry["test_tool"] == ("test_mcp", "test_tool")

    async def test_register_mcp_handles_initialization_error(self, mcp_manager, mock_mcp_plugin):
        """Test that register_mcp handles initialization errors"""
        mock_mcp_plugin.initialize = AsyncMock(side_effect=Exception("Init failed"))

        with pytest.raises(Exception, match="Init failed"):
            await mcp_manager.register_mcp(mock_mcp_plugin)

        # MCP should not be registered
        assert "test_mcp" not in mcp_manager.mcps

    async def test_execute_tool_calls_correct_mcp(self, mcp_manager, mock_mcp_plugin):
        """Test that execute_tool calls the correct MCP plugin"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        result = await mcp_manager.execute_tool(
            tool_name="test_tool",
            parameters={"query": "test"}
        )

        mock_mcp_plugin.execute_tool.assert_called_once_with(
            "test_tool",
            {"query": "test"}
        )
        assert "result" in result

    async def test_execute_tool_raises_error_for_unknown_tool(self, mcp_manager):
        """Test that execute_tool raises error for unknown tool"""
        with pytest.raises(ValueError, match="Tool not found: unknown_tool"):
            await mcp_manager.execute_tool(
                tool_name="unknown_tool",
                parameters={}
            )

    async def test_get_all_tools_returns_all_enabled_tools(self, mcp_manager, mock_mcp_plugin):
        """Test that get_all_tools returns tools from all enabled MCPs"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        tools = await mcp_manager.get_all_tools()

        assert len(tools) == 1
        assert tools[0]["function"]["name"] == "test_tool"

    async def test_get_all_tools_excludes_disabled_mcps(self, mcp_manager, mock_mcp_plugin):
        """Test that get_all_tools excludes disabled MCPs"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        # Disable the MCP
        mock_mcp_plugin.enabled = False

        tools = await mcp_manager.get_all_tools()

        assert len(tools) == 0

    async def test_get_all_tools_with_multiple_mcps(self, mcp_manager, mock_mcp_plugin):
        """Test get_all_tools with multiple MCP plugins"""
        # Register first MCP
        await mcp_manager.register_mcp(mock_mcp_plugin)

        # Create and register second MCP
        mcp2 = AsyncMock(spec=BaseMCP)
        mcp2.name = "mcp2"
        mcp2.enabled = True

        async def mock_get_tools2():
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "tool2",
                        "description": "Second tool"
                    }
                }
            ]

        mcp2.initialize = AsyncMock()
        mcp2.get_tools = AsyncMock(side_effect=mock_get_tools2)

        await mcp_manager.register_mcp(mcp2)

        tools = await mcp_manager.get_all_tools()

        assert len(tools) == 2
        tool_names = [t["function"]["name"] for t in tools]
        assert "test_tool" in tool_names
        assert "tool2" in tool_names

    async def test_gather_context_calls_all_mcps(self, mcp_manager, mock_mcp_plugin):
        """Test that gather_context calls get_context on all MCPs"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        context = await mcp_manager.gather_context("test query")

        assert "test_mcp" in context
        mock_mcp_plugin.get_context.assert_called_once_with("test query")

    async def test_gather_context_with_specific_mcps(self, mcp_manager, mock_mcp_plugin):
        """Test that gather_context can query specific MCPs only"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        # Create second MCP but don't include it in active list
        mcp2 = AsyncMock(spec=BaseMCP)
        mcp2.name = "mcp2"
        mcp2.enabled = True
        mcp2.initialize = AsyncMock()
        mcp2.get_tools = AsyncMock(return_value=[])
        mcp2.get_context = AsyncMock(return_value={"data": "from mcp2"})

        await mcp_manager.register_mcp(mcp2)

        # Only query test_mcp
        context = await mcp_manager.gather_context(
            "test query",
            active_mcps=["test_mcp"]
        )

        assert "test_mcp" in context
        assert "mcp2" not in context
        mock_mcp_plugin.get_context.assert_called_once()
        mcp2.get_context.assert_not_called()

    async def test_gather_context_handles_mcp_errors(self, mcp_manager, mock_mcp_plugin):
        """Test that gather_context handles errors from individual MCPs"""
        mock_mcp_plugin.get_context = AsyncMock(side_effect=Exception("Context error"))

        await mcp_manager.register_mcp(mock_mcp_plugin)

        # Should not raise, just skip the failed MCP
        context = await mcp_manager.gather_context("test query")

        # Context should be empty since the only MCP failed
        assert context == {}

    async def test_gather_context_skips_disabled_mcps(self, mcp_manager, mock_mcp_plugin):
        """Test that gather_context skips disabled MCPs"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        # Disable the MCP
        mock_mcp_plugin.enabled = False

        context = await mcp_manager.gather_context("test query")

        assert context == {}
        mock_mcp_plugin.get_context.assert_not_called()

    async def test_shutdown_all_calls_shutdown_on_all_mcps(self, mcp_manager, mock_mcp_plugin):
        """Test that shutdown_all calls shutdown on all MCPs"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        await mcp_manager.shutdown_all()

        mock_mcp_plugin.shutdown.assert_called_once()

    async def test_shutdown_all_handles_errors(self, mcp_manager, mock_mcp_plugin):
        """Test that shutdown_all handles errors from individual MCPs"""
        mock_mcp_plugin.shutdown = AsyncMock(side_effect=Exception("Shutdown error"))

        await mcp_manager.register_mcp(mock_mcp_plugin)

        # Should not raise
        await mcp_manager.shutdown_all()

        mock_mcp_plugin.shutdown.assert_called_once()

    def test_get_mcp_returns_registered_mcp(self, mcp_manager, mock_mcp_plugin):
        """Test that get_mcp returns the correct MCP"""
        # Synchronously add to mcps dict (skip async register for this test)
        mcp_manager.mcps["test_mcp"] = mock_mcp_plugin

        mcp = mcp_manager.get_mcp("test_mcp")

        assert mcp == mock_mcp_plugin

    def test_get_mcp_returns_none_for_unknown_mcp(self, mcp_manager):
        """Test that get_mcp returns None for unknown MCP"""
        mcp = mcp_manager.get_mcp("unknown_mcp")

        assert mcp is None

    def test_list_mcps_returns_metadata(self, mcp_manager, mock_mcp_plugin):
        """Test that list_mcps returns metadata for all MCPs"""
        mcp_manager.mcps["test_mcp"] = mock_mcp_plugin

        mcps_list = mcp_manager.list_mcps()

        assert len(mcps_list) == 1
        assert mcps_list[0] == mock_mcp_plugin.metadata

    def test_list_mcps_returns_empty_when_no_mcps(self, mcp_manager):
        """Test that list_mcps returns empty list when no MCPs registered"""
        mcps_list = mcp_manager.list_mcps()

        assert mcps_list == []

    async def test_register_multiple_mcps_with_different_tools(self, mcp_manager, mock_mcp_plugin):
        """Test registering multiple MCPs with different tools"""
        # Register first MCP
        await mcp_manager.register_mcp(mock_mcp_plugin)

        # Create and register second MCP with different tool
        mcp2 = AsyncMock(spec=BaseMCP)
        mcp2.name = "mcp2"
        mcp2.enabled = True
        mcp2.metadata = {"name": "mcp2", "version": "1.0"}

        async def mock_get_tools2():
            return [
                {
                    "type": "function",
                    "function": {
                        "name": "different_tool",
                        "description": "A different tool"
                    }
                }
            ]

        mcp2.initialize = AsyncMock()
        mcp2.get_tools = AsyncMock(side_effect=mock_get_tools2)

        await mcp_manager.register_mcp(mcp2)

        # Verify both tools are registered
        assert "test_tool" in mcp_manager.tool_registry
        assert "different_tool" in mcp_manager.tool_registry

        # Verify they map to different MCPs
        assert mcp_manager.tool_registry["test_tool"][0] == "test_mcp"
        assert mcp_manager.tool_registry["different_tool"][0] == "mcp2"

    async def test_execute_tool_with_complex_parameters(self, mcp_manager, mock_mcp_plugin):
        """Test execute_tool with complex nested parameters"""
        await mcp_manager.register_mcp(mock_mcp_plugin)

        complex_params = {
            "query": "test",
            "options": {
                "nested": True,
                "values": [1, 2, 3]
            }
        }

        result = await mcp_manager.execute_tool(
            tool_name="test_tool",
            parameters=complex_params
        )

        mock_mcp_plugin.execute_tool.assert_called_once_with(
            "test_tool",
            complex_params
        )
