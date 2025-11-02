"""MCP Manager"""

from typing import Dict, Any, List, Optional, Tuple
import structlog

from bot.mcp.base import BaseMCP

logger = structlog.get_logger()


class MCPManager:
    """Manages all MCP plugins"""
    
    def __init__(self):
        self.mcps: Dict[str, BaseMCP] = {}
        self.tool_registry: Dict[str, Tuple[str, str]] = {}  # tool_name -> (mcp_name, tool_name)
    
    async def register_mcp(self, mcp: BaseMCP) -> None:
        """Register a new MCP plugin"""
        try:
            await mcp.initialize()
            self.mcps[mcp.name] = mcp
            
            # Register tools
            tools = await mcp.get_tools()
            for tool in tools:
                if "function" in tool:
                    tool_name = tool["function"]["name"]
                else:
                    tool_name = tool.get("name", "")
                
                if tool_name:
                    self.tool_registry[tool_name] = (mcp.name, tool_name)
            
            logger.info(f"Registered MCP: {mcp.name} with {len(tools)} tools")
            
        except Exception as e:
            logger.error(f"Failed to register MCP {mcp.name}: {e}")
            raise
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a tool from any registered MCP"""
        if tool_name not in self.tool_registry:
            raise ValueError(f"Tool not found: {tool_name}")
        
        mcp_name, _ = self.tool_registry[tool_name]
        mcp = self.mcps[mcp_name]
        
        logger.info(f"Executing tool: {tool_name} from MCP: {mcp_name}")
        
        return await mcp.execute_tool(tool_name, parameters)
    
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools from all MCPs"""
        all_tools = []
        for mcp in self.mcps.values():
            if mcp.enabled:
                tools = await mcp.get_tools()
                all_tools.extend(tools)
        return all_tools
    
    async def gather_context(
        self,
        user_query: str,
        active_mcps: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Gather context from specified or all MCPs"""
        context = {}
        
        mcps_to_query = active_mcps if active_mcps else list(self.mcps.keys())
        
        for mcp_name in mcps_to_query:
            if mcp_name in self.mcps and self.mcps[mcp_name].enabled:
                try:
                    mcp_context = await self.mcps[mcp_name].get_context(user_query)
                    context[mcp_name] = mcp_context
                except Exception as e:
                    logger.error(f"Failed to get context from {mcp_name}: {e}")
        
        return context
    
    async def shutdown_all(self) -> None:
        """Shutdown all MCPs"""
        for mcp in self.mcps.values():
            try:
                await mcp.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down {mcp.name}: {e}")
    
    def get_mcp(self, name: str) -> Optional[BaseMCP]:
        """Get MCP by name"""
        return self.mcps.get(name)
    
    def list_mcps(self) -> List[Dict[str, Any]]:
        """List all registered MCPs"""
        return [mcp.metadata for mcp in self.mcps.values()]
