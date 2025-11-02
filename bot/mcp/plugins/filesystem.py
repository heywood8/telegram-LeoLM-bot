"""File System MCP Plugin"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import aiofiles
import structlog

from bot.mcp.base import BaseMCP

logger = structlog.get_logger()


class FileSystemMCP(BaseMCP):
    """MCP for file system operations"""
    
    version = "1.0.0"
    description = "Provides file system access and operations"
    
    async def initialize(self) -> bool:
        self.base_path = Path(self.config.get("base_path", "/tmp/bot_workspace"))
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileSystemMCP initialized with base_path: {self.base_path}")
        return True
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file to read"
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to file"},
                            "content": {"type": "string", "description": "Content to write"}
                        },
                        "required": ["file_path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List contents of a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "Directory path (default: root)"
                            }
                        }
                    }
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "read_file":
            return await self._read_file(parameters["file_path"])
        elif tool_name == "write_file":
            return await self._write_file(parameters["file_path"], parameters["content"])
        elif tool_name == "list_directory":
            return await self._list_directory(parameters.get("directory", "."))
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def get_context(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Provide file system context"""
        return {
            "base_path": str(self.base_path),
            "available_operations": ["read", "write", "list"]
        }
    
    async def _read_file(self, file_path: str) -> str:
        """Read file contents"""
        full_path = self.base_path / file_path
        
        # Security check
        if not self._is_safe_path(full_path):
            raise ValueError("Access denied: path outside workspace")
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        async with aiofiles.open(full_path, 'r') as f:
            content = await f.read()
        
        logger.info(f"Read file: {file_path}, size: {len(content)}")
        return content
    
    async def _write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Write to file"""
        full_path = self.base_path / file_path
        
        # Security check
        if not self._is_safe_path(full_path):
            raise ValueError("Access denied: path outside workspace")
        
        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(full_path, 'w') as f:
            await f.write(content)
        
        logger.info(f"Wrote file: {file_path}, size: {len(content)}")
        
        return {
            "success": True,
            "path": str(full_path),
            "size": len(content)
        }
    
    async def _list_directory(self, directory: str) -> List[Dict[str, Any]]:
        """List directory contents"""
        full_path = self.base_path / directory
        
        # Security check
        if not self._is_safe_path(full_path):
            raise ValueError("Access denied: path outside workspace")
        
        if not full_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not full_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        items = []
        for item in full_path.iterdir():
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            })
        
        logger.info(f"Listed directory: {directory}, items: {len(items)}")
        return items
    
    def _is_safe_path(self, path: Path) -> bool:
        """Check if path is within base_path"""
        try:
            path.resolve().relative_to(self.base_path.resolve())
            return True
        except ValueError:
            return False
