"""Base MCP (Model Context Protocol) framework"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import structlog

logger = structlog.get_logger()


class BaseMCP(ABC):
    """Abstract base class for all MCP plugins"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = True
        self.version = getattr(self, "version", "1.0.0")
        self.description = getattr(self, "description", "")
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize MCP plugin"""
        pass
    
    @abstractmethod
    async def get_tools(self) -> List[Dict[str, Any]]:
        """Return list of available tools in OpenAI function format"""
        pass
    
    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a specific tool"""
        pass
    
    @abstractmethod
    async def get_context(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve contextual information"""
        pass
    
    async def shutdown(self) -> None:
        """Cleanup resources"""
        pass
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Return MCP metadata"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
        }
