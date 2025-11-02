# Telegram LLM Bot with MCP Integration - Design Document

**Version:** 1.0  
**Date:** October 22, 2025  
**Status:** Design Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [LLM Integration](#llm-integration)
5. [MCP (Model Context Protocol) Framework](#mcp-model-context-protocol-framework)
6. [Data Flow](#data-flow)
7. [Security & Privacy](#security--privacy)
8. [Scalability & Performance](#scalability--performance)
9. [Deployment Strategy](#deployment-strategy)
10. [Development Roadmap](#development-roadmap)
11. [Technical Stack](#technical-stack)
12. [API Specifications](#api-specifications)
13. [Testing Strategy](#testing-strategy)
14. [Monitoring & Observability](#monitoring--observability)

---

## Executive Summary

### Purpose
A highly extensible Telegram bot that leverages open-source Large Language Models (currently using Ollama with gpt-oss:120b-cloud model) to provide intelligent conversational experiences. The bot is designed with a plugin-based MCP (Model Context Protocol) architecture to allow seamless integration of various context providers and tools.

### Key Features
- **LLM-Powered Conversations**: Natural language understanding using Ollama (swappable provider architecture)
- **MCP Extensibility**: Plugin architecture for adding custom context providers
- **Multi-User Support**: Concurrent user handling with isolated contexts
- **Context Management**: Conversation history and session management
- **Rich Media Support**: Text, images, documents, and voice messages
- **Rate Limiting**: Protection against abuse
- **Admin Controls**: Management interface for bot operators

### Design Goals
1. **Modularity**: Clean separation between bot logic, LLM integration, and MCP plugins
2. **Extensibility**: Easy addition of new MCP providers without core modifications
3. **Scalability**: Support for thousands of concurrent users
4. **Reliability**: Fault tolerance and graceful degradation
5. **Maintainability**: Clear code structure and comprehensive documentation

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Telegram Platform                         │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ Webhook/Polling
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Bot Application Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │   Handler    │  │   Session    │  │   Rate Limiter      │  │
│  │   Manager    │──┤   Manager    │  │   & Middleware      │  │
│  └──────────────┘  └──────────────┘  └─────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
         ┌────────────────────┐  ┌─────────────────┐
         │   LLM Integration  │  │  MCP Framework  │
         │      Layer         │  │     Layer       │
         └──────────┬─────────┘  └────────┬────────┘
                    │                     │
                    ▼                     ▼
         ┌────────────────────┐  ┌─────────────────────────┐
         │  Ollama Provider   │  │   MCP Plugin Manager   │
         │   (Swappable)      │  │  (Currently disabled)   │
         └────────────────────┘  │  ┌─────────────────┐   │
                                 │  │ File System MCP │   │
                                 │  ├─────────────────┤   │
                                 │  │   Database MCP  │   │
                                 │  ├─────────────────┤   │
                                 │  │    Custom MCP   │   │
                                 │  └─────────────────┘   │
                                 └─────────────────────────┘
                                          │
                    ┌─────────────────────┼────────────────┐
                    ▼                     ▼                ▼
         ┌──────────────────┐  ┌─────────────┐  ┌────────────┐
         │   PostgreSQL     │  │    Redis    │  │  External  │
         │  (Persistent)    │  │   (Cache)   │  │   APIs     │
         └──────────────────┘  └─────────────┘  └────────────┘
```

### Component Interaction Flow

1. **User Input** → Telegram → Bot Handler
2. **Bot Handler** → Session Manager (load context)
3. **Session Manager** → MCP Framework (gather context) - *Currently disabled*
4. **MCP Framework** → Active MCP Plugins (execute tools/queries) - *Currently disabled*
5. **Bot Handler** → LLM Integration (process with context)
6. **LLM Integration** → Ollama Provider (generate response)
7. **Response** → Bot Handler → Telegram → User

---

## Core Components

### 1. Bot Handler Layer

**Responsibility**: Interface with Telegram API and route messages

#### Components:
- **Message Router**: Routes incoming messages to appropriate handlers
- **Command Handler**: Processes bot commands (/start, /help, /reset, etc.)
- **Conversation Handler**: Manages conversational state machines
- **Media Handler**: Processes images, documents, voice messages
- **Error Handler**: Catches and logs exceptions, provides user feedback

#### Key Classes:
```python
class TelegramBotHandler:
    """Main bot handler orchestrating all interactions"""
    
    def __init__(self, token: str, config: BotConfig):
        self.application = ApplicationBuilder().token(token).build()
        self.session_manager = SessionManager()
        self.llm_service = LLMService()
        self.mcp_manager = MCPManager()
        self.rate_limiter = RateLimiter()
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process incoming message"""
        pass
    
    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process bot commands"""
        pass
```

### 2. Session Manager

**Responsibility**: Manage user sessions, context, and conversation history

#### Features:
- Per-user conversation history
- Context windowing (manage token limits)
- Session persistence
- Multi-turn conversation tracking
- User preferences storage

#### Key Classes:
```python
class SessionManager:
    """Manages user sessions and conversation context"""
    
    def __init__(self, db_connection, cache_connection):
        self.db = db_connection
        self.cache = cache_connection
        self.sessions = {}
    
    async def get_session(self, user_id: int) -> UserSession:
        """Retrieve or create user session"""
        pass
    
    async def update_context(self, user_id: int, message: Message):
        """Add message to conversation history"""
        pass
    
    async def get_context_window(self, user_id: int, max_tokens: int) -> List[Message]:
        """Get recent messages within token limit"""
        pass
    
    def clear_session(self, user_id: int):
        """Reset user conversation"""
        pass
```

#### Data Structure:
```python
@dataclass
class UserSession:
    user_id: int
    created_at: datetime
    last_active: datetime
    conversation_history: List[Message]
    active_mcps: List[str]
    preferences: Dict[str, Any]
    metadata: Dict[str, Any]
```

### 3. Rate Limiter & Middleware

**Responsibility**: Protect against abuse and manage resource usage

#### Features:
- Per-user rate limiting
- Global rate limiting
- Cost tracking (LLM API calls)
- Request queuing
- Graceful degradation

#### Implementation:
```python
class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.user_limits = RateLimitConfig.USER_LIMITS
        self.global_limits = RateLimitConfig.GLOBAL_LIMITS
    
    async def check_limit(self, user_id: int) -> Tuple[bool, Optional[int]]:
        """Check if user can make request, return (allowed, retry_after)"""
        pass
    
    async def consume_token(self, user_id: int):
        """Consume a rate limit token"""
        pass
```

---

## LLM Integration

### Architecture

The LLM integration layer is designed to be **model-agnostic**, allowing easy swapping between different models.

### Abstract LLM Interface

```python
from abc import ABC, abstractmethod
from typing import List, Optional, AsyncGenerator

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response from LLM"""
        pass
    
    @abstractmethod
    async def get_embeddings(self, text: str) -> List[float]:
        """Get text embeddings"""
        pass
    
    @abstractmethod
    def get_token_count(self, text: str) -> int:
        """Count tokens in text"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if LLM service is available"""
        pass
```

### Ollama Provider Implementation

```python
class OllamaProvider(BaseLLMProvider):
    """Ollama provider implementation"""
    
    def __init__(self, config: LLMConfig):
        self.base_url = config.base_url
        self.model_name = config.model_name
        self.api_key = config.api_key
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
        self.tokenizer = self._load_tokenizer()
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
    """Generate response using Ollama"""
        
        try:
            if stream:
                return self._stream_generate(messages, temperature, max_tokens, tools)
            else:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise LLMError(f"Failed to generate response: {str(e)}")
    
    async def _stream_generate(self, messages, temperature, max_tokens, tools):
        """Stream response tokens"""
        async for chunk in await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            stream=True
        ):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

### LLM Service Layer

```python
class LLMService:
    """High-level LLM service orchestrator"""
    
    def __init__(self, provider: BaseLLMProvider, config: ServiceConfig):
        self.provider = provider
        self.config = config
        self.system_prompt = self._load_system_prompt()
    
    async def process_message(
        self,
        user_message: str,
        context: List[Dict[str, str]],
        mcp_context: Optional[Dict] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Process user message with context and MCP data"""
        
        # Build messages array
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add conversation history
        messages.extend(context)
        
        # Inject MCP context if available
        if mcp_context:
            mcp_content = self._format_mcp_context(mcp_context)
            messages.append({
                "role": "system",
                "content": f"Additional context from tools:\n{mcp_content}"
            })
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Generate response
        return await self.provider.generate(
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=stream
        )
    
    def _format_mcp_context(self, mcp_context: Dict) -> str:
        """Format MCP context for injection into prompt"""
        formatted = []
        for mcp_name, data in mcp_context.items():
            formatted.append(f"[{mcp_name}]")
            formatted.append(json.dumps(data, indent=2))
        return "\n\n".join(formatted)
```

### Configuration

```python
@dataclass
class LLMConfig:
    model_name: str = "gpt-oss:120b-cloud"
    base_url: str = "https://ollama.com/v1"
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 60
    retry_attempts: int = 3
    retry_delay: float = 1.0
```

---

## MCP (Model Context Protocol) Framework

### Overview

The MCP Framework allows the bot to extend its capabilities by integrating various context providers and tools. Each MCP is a self-contained plugin that can:

- Provide contextual information to the LLM
- Execute actions/tools based on LLM requests
- Access external systems (databases, APIs, file systems, etc.)

### MCP Architecture

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseMCP(ABC):
    """Abstract base class for all MCP plugins"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = True
    
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
    
    async def shutdown(self):
        """Cleanup resources"""
        pass
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Return MCP metadata"""
        return {
            "name": self.name,
            "version": getattr(self, "version", "1.0.0"),
            "description": getattr(self, "description", ""),
            "enabled": self.enabled
        }
```

### MCP Manager

```python
class MCPManager:
    """Manages all MCP plugins"""
    
    def __init__(self, config: MCPConfig):
        self.config = config
        self.mcps: Dict[str, BaseMCP] = {}
        self.tool_registry: Dict[str, Tuple[str, str]] = {}  # tool_name -> (mcp_name, tool_name)
    
    async def register_mcp(self, mcp: BaseMCP):
        """Register a new MCP plugin"""
        try:
            await mcp.initialize()
            self.mcps[mcp.name] = mcp
            
            # Register tools
            tools = await mcp.get_tools()
            for tool in tools:
                tool_name = tool["name"]
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
        
        return await mcp.execute_tool(tool_name, parameters)
    
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools from all MCPs"""
        all_tools = []
        for mcp in self.mcps.values():
            if mcp.enabled:
                tools = await mcp.get_tools()
                all_tools.extend(tools)
        return all_tools
    
    async def gather_context(self, user_query: str, active_mcps: Optional[List[str]] = None) -> Dict[str, Any]:
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
    
    async def shutdown_all(self):
        """Shutdown all MCPs"""
        for mcp in self.mcps.values():
            await mcp.shutdown()
```

### Built-in MCP Plugins

#### 1. File System MCP

```python
class FileSystemMCP(BaseMCP):
    """MCP for file system operations"""
    
    version = "1.0.0"
    description = "Provides file system access and operations"
    
    async def initialize(self) -> bool:
        self.base_path = Path(self.config.get("base_path", "/tmp/bot_workspace"))
        self.base_path.mkdir(parents=True, exist_ok=True)
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
                            "file_path": {"type": "string"},
                            "content": {"type": "string"}
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
                            "directory": {"type": "string"}
                        },
                        "required": ["directory"]
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
            return await self._list_directory(parameters["directory"])
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
        if not full_path.is_relative_to(self.base_path):
            raise ValueError("Access denied: path outside workspace")
        
        async with aiofiles.open(full_path, 'r') as f:
            return await f.read()
    
    async def _write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Write to file"""
        full_path = self.base_path / file_path
        if not full_path.is_relative_to(self.base_path):
            raise ValueError("Access denied: path outside workspace")
        
        full_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full_path, 'w') as f:
            await f.write(content)
        
        return {"success": True, "path": str(full_path)}
    
    async def _list_directory(self, directory: str) -> List[str]:
        """List directory contents"""
        full_path = self.base_path / directory
        if not full_path.is_relative_to(self.base_path):
            raise ValueError("Access denied: path outside workspace")
        
        return [item.name for item in full_path.iterdir()]
```

#### 2. Database MCP

```python
class DatabaseMCP(BaseMCP):
    """MCP for database operations"""
    
    version = "1.0.0"
    description = "Provides database query and manipulation capabilities"
    
    async def initialize(self) -> bool:
        self.db_url = self.config["database_url"]
        self.engine = create_async_engine(self.db_url)
        return True
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_database",
                    "description": "Execute a SELECT query on the database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL SELECT query to execute"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_schema",
                    "description": "Get database schema information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "Specific table name (optional)"
                            }
                        }
                    }
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "query_database":
            return await self._execute_query(parameters["query"])
        elif tool_name == "get_schema":
            return await self._get_schema(parameters.get("table_name"))
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def get_context(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Provide database context"""
        return {
            "available_tables": await self._get_table_list(),
            "connection_status": "connected"
        }
    
    async def _execute_query(self, query: str) -> List[Dict]:
        """Execute SQL query (read-only)"""
        # Validate query is SELECT only
        if not query.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")
        
        async with self.engine.begin() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]
    
    async def _get_schema(self, table_name: Optional[str] = None) -> Dict:
        """Get schema information"""
        # Implementation for schema retrieval
        pass
    
    async def shutdown(self):
        await self.engine.dispose()
```

#### 3. Web Search MCP (Example - Removed)

**Note:** The built-in Web Search MCP has been removed. For web search functionality, integrate an external MCP service or implement a custom plugin.

```python
class WebSearchMCP(BaseMCP):
    """Example MCP for web search capabilities (removed from codebase)"""
    
    version = "1.0.0"
    description = "Provides web search and scraping capabilities"
    
    async def initialize(self) -> bool:
        self.api_key = self.config.get("search_api_key")
        self.search_engine = self.config.get("search_engine", "duckduckgo")
        return True
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "Number of results to return",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_webpage",
                    "description": "Fetch and extract content from a webpage",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"}
                        },
                        "required": ["url"]
                    }
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "web_search":
            return await self._web_search(parameters["query"], parameters.get("num_results", 5))
        elif tool_name == "fetch_webpage":
            return await self._fetch_webpage(parameters["url"])
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def get_context(self, query: Optional[str] = None) -> Dict[str, Any]:
        return {
            "search_engine": self.search_engine,
            "available": True
        }
    
    async def _web_search(self, query: str, num_results: int) -> List[Dict]:
        """Perform web search"""
        # Implementation using search API
        pass
    
    async def _fetch_webpage(self, url: str) -> str:
        """Fetch webpage content"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html = await response.text()
                # Extract main content using BeautifulSoup or similar
                return self._extract_content(html)
```

#### 4. Custom MCP Template

```python
class CustomMCP(BaseMCP):
    """Template for creating custom MCP plugins"""
    
    version = "1.0.0"
    description = "Your custom MCP description"
    
    async def initialize(self) -> bool:
        """Setup your MCP"""
        # Initialize resources, connections, etc.
        return True
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        """Define your tools in OpenAI function format"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "your_tool_name",
                    "description": "What your tool does",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "param1": {"type": "string", "description": "First parameter"}
                        },
                        "required": ["param1"]
                    }
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute your tool"""
        if tool_name == "your_tool_name":
            return await self._your_tool_implementation(parameters)
        raise ValueError(f"Unknown tool: {tool_name}")
    
    async def get_context(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Provide context to the LLM"""
        return {"your_context_key": "your_context_value"}
    
    async def _your_tool_implementation(self, parameters: Dict[str, Any]) -> Any:
        """Your actual tool logic"""
        pass
```

### MCP Configuration

```python
@dataclass
class MCPConfig:
    enabled_mcps: List[str]
    mcp_configs: Dict[str, Dict[str, Any]]
    auto_load: bool = True
    plugin_directory: str = "./mcps"

# Example configuration (currently disabled in codebase)
mcp_config = MCPConfig(
    enabled_mcps=[],  # Currently all MCPs are disabled (0 registered plugins)
    mcp_configs={
        "FileSystemMCP": {
            "base_path": "/tmp/bot_workspace"
        },
        "DatabaseMCP": {
            "database_url": "postgresql://user:pass@localhost/db"
        }
        # WebSearchMCP removed from codebase
    }
)
```

---

## Data Flow

### Complete Message Flow

```
1. User sends message to Telegram bot
   ↓
2. Telegram sends update to bot (webhook or polling)
   ↓
3. Bot Handler receives update
   ↓
4. Rate Limiter checks if user can proceed
   ↓
5. Session Manager loads user session and context
   ↓
6. MCP Manager gathers context from active MCPs
   ↓
7. LLM Service formats prompt with:
   - System prompt
   - Conversation history
   - MCP context
   - User message
   ↓
8. LLM Provider (Ollama) generates response
   ↓
9. If LLM requests tool use:
   - MCP Manager executes tool
   - Result fed back to LLM
   - LLM generates final response
   ↓
10. Bot Handler sends response to user
    ↓
11. Session Manager updates conversation history
    ↓
12. Response displayed in Telegram
```

### Tool Execution Flow

```
LLM requests tool → Bot Handler detects tool call
                    ↓
                    MCP Manager identifies target MCP
                    ↓
                    MCP executes tool
                    ↓
                    Result formatted and returned
                    ↓
                    Result sent back to LLM with context
                    ↓
                    LLM generates response using tool result
                    ↓
                    Final response sent to user
```

---

## Security & Privacy

### Authentication & Authorization

```python
class SecurityManager:
    """Manages bot security"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.admin_users = set(config.admin_user_ids)
        self.blocked_users = set()
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.admin_users
    
    def is_blocked(self, user_id: int) -> bool:
        """Check if user is blocked"""
        return user_id in self.blocked_users
    
    async def validate_request(self, update: Update) -> bool:
        """Validate incoming request"""
        user_id = update.effective_user.id
        
        if self.is_blocked(user_id):
            return False
        
        # Additional validation logic
        return True
```

### Data Privacy

1. **Message Encryption**: All messages stored encrypted at rest
2. **Data Retention**: Configurable retention policy (default: 30 days)
3. **User Data Deletion**: Support for GDPR-compliant data deletion
4. **Audit Logging**: All sensitive operations logged
5. **PII Detection**: Automatic detection and masking of sensitive information

### Security Best Practices

1. **Input Sanitization**: All user inputs sanitized before processing
2. **Output Validation**: LLM outputs validated before sending
3. **Resource Limits**: Strict limits on file sizes, query complexity
4. **Sandboxing**: MCP operations run in isolated environments
5. **API Key Management**: Secure storage using environment variables/secrets manager

```python
class InputSanitizer:
    """Sanitize user inputs"""
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Remove potentially harmful content"""
        # Remove control characters
        text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
        # Limit length
        return text[:4096]
    
    @staticmethod
    def sanitize_file_path(path: str) -> str:
        """Ensure file path is safe"""
        # Prevent directory traversal
        path = path.replace('../', '').replace('..\\', '')
        return Path(path).name
```

---

## Scalability & Performance

### Horizontal Scaling

The bot is designed to scale horizontally:

1. **Stateless Design**: Session data stored in Redis/PostgreSQL
2. **Load Balancing**: Multiple bot instances behind load balancer
3. **Queue-Based Processing**: Redis queues for async task processing
4. **Webhook Distribution**: Telegram webhooks distributed across instances

### Performance Optimization

```python
class PerformanceOptimizer:
    """Performance optimization strategies"""
    
    def __init__(self):
        self.cache = Redis()
        self.metrics = MetricsCollector()
    
    async def cache_llm_response(self, prompt_hash: str, response: str):
        """Cache similar prompts"""
        await self.cache.setex(
            f"llm:cache:{prompt_hash}",
            3600,  # 1 hour TTL
            response
        )
    
    async def get_cached_response(self, prompt_hash: str) -> Optional[str]:
        """Retrieve cached response"""
        return await self.cache.get(f"llm:cache:{prompt_hash}")
```

### Resource Management

```python
@dataclass
class ResourceLimits:
    max_message_length: int = 4096
    max_history_messages: int = 50
    max_context_tokens: int = 8000
    max_file_size: int = 20 * 1024 * 1024  # 20 MB
    max_concurrent_llm_calls: int = 10
    max_mcp_execution_time: int = 30  # seconds
```

### Caching Strategy

1. **LLM Response Caching**: Cache similar prompts/responses
2. **Session Caching**: Redis for fast session retrieval
3. **MCP Context Caching**: Cache expensive MCP operations
4. **Static Content Caching**: Cache system prompts, configurations

---

## Deployment Strategy

### Container Architecture

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "bot.main"]
```

### Docker Compose Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot:
    build: .
    env_file: .env
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    volumes:
      - ./data:/app/data
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 2G

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: telegram_bot
      POSTGRES_USER: botuser
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  llm_server:
    image: vllm/vllm-openai:latest
    environment:
      MODEL_NAME: gpt-oss-20b
    volumes:
      - ./models:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - bot
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes Deployment

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: telegram-bot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: telegram-bot
  template:
    metadata:
      labels:
        app: telegram-bot
    spec:
      containers:
      - name: bot
        image: telegram-bot:latest
        envFrom:
        - configMapRef:
            name: bot-config
        - secretRef:
            name: bot-secrets
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
          requests:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Environment Configuration

```bash
# .env.example
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook

# LLM Configuration
LLM_PROVIDER=gpt-oss-20b
LLM_BASE_URL=http://llm-server:8000/v1
LLM_MODEL_NAME=gpt-oss-20b
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048

# Database
DATABASE_URL=postgresql://botuser:password@postgres:5432/telegram_bot

# Redis
REDIS_URL=redis://redis:6379/0

# MCP Configuration (currently disabled)
# MCP_FILESYSTEM_ENABLED=false
# MCP_FILESYSTEM_BASE_PATH=/app/workspace
# MCP_DATABASE_ENABLED=false
# Note: MCP_WEBSEARCH removed from codebase

# Security
ADMIN_USER_IDS=123456789,987654321
SECRET_KEY=your_secret_key_here

# Rate Limiting
RATE_LIMIT_USER_REQUESTS=20
RATE_LIMIT_USER_WINDOW=60
RATE_LIMIT_GLOBAL_REQUESTS=100

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## Development Roadmap

### Phase 1: Foundation (Weeks 1-4)

**Goals**: Core bot functionality with basic LLM integration

- [ ] Project setup and structure
- [ ] Telegram bot basic handlers
- [ ] Session management implementation
- [ ] LLM integration layer (abstract + GPT-OSS)
- [ ] Database models and migrations
- [ ] Configuration management
- [ ] Basic logging and error handling
- [ ] Unit tests for core components

**Deliverables**:
- Working bot that can respond to messages using Ollama
- Basic session management
- Database persistence

### Phase 2: MCP Framework (Weeks 5-8)

**Goals**: Implement MCP architecture and core plugins

- [ ] MCP base classes and interfaces
- [ ] MCP Manager implementation
- [ ] Tool calling integration with LLM
- [ ] File System MCP
- [ ] Database MCP
- [ ] Web Search MCP
- [ ] MCP testing framework
- [ ] Documentation for MCP development

**Deliverables**:
- Fully functional MCP framework
- Three working MCP plugins
- Developer documentation for creating custom MCPs

### Phase 3: Advanced Features (Weeks 9-12)

**Goals**: Production-ready features

- [ ] Rate limiting system
- [ ] Advanced session management (context windowing)
- [ ] Streaming responses
- [ ] Rich media support (images, documents, voice)
- [ ] Admin commands and controls
- [ ] User preferences system
- [ ] Conversation export functionality
- [ ] Enhanced error recovery

**Deliverables**:
- Production-ready bot with all core features
- Admin interface
- User documentation

### Phase 4: Optimization & Scaling (Weeks 13-16)

**Goals**: Performance, scalability, and deployment

- [ ] Performance profiling and optimization
- [ ] Caching layer implementation
- [ ] Horizontal scaling support
- [ ] Load testing
- [ ] Docker containerization
- [ ] Kubernetes manifests
- [ ] CI/CD pipeline
- [ ] Monitoring and alerting setup

**Deliverables**:
- Scalable deployment configuration
- Performance benchmarks
- Production deployment guide

### Phase 5: Extended MCPs (Weeks 17-20)

**Goals**: Additional MCP plugins and integrations

- [ ] Calendar/Schedule MCP
- [ ] Email MCP
- [ ] GitHub Integration MCP
- [ ] Code Execution MCP (sandboxed)
- [ ] Weather/News MCP
- [ ] Translation MCP
- [ ] Image Generation MCP
- [ ] Plugin marketplace/registry

**Deliverables**:
- 5+ additional MCP plugins
- MCP discovery and installation system

---

## Technical Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Language** | Python | 3.11+ | Main development language |
| **Bot Framework** | python-telegram-bot | 20.x | Telegram API wrapper |
| **LLM Server** | vLLM | latest | LLM inference server |
| **Web Framework** | FastAPI | 0.104+ | Webhook server & API |
| **Database** | PostgreSQL | 15+ | Persistent storage |
| **Cache** | Redis | 7+ | Session cache, queues |
| **ORM** | SQLAlchemy | 2.0+ | Database ORM |
| **HTTP Client** | aiohttp | 3.9+ | Async HTTP requests |
| **Task Queue** | Celery | 5.3+ | Background task processing |

### Development Tools

| Tool | Purpose |
|------|---------|
| **Poetry** | Dependency management |
| **Black** | Code formatting |
| **Ruff** | Linting |
| **MyPy** | Type checking |
| **Pytest** | Testing framework |
| **pytest-asyncio** | Async testing |
| **pytest-cov** | Code coverage |
| **Pre-commit** | Git hooks |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| **Container Runtime** | Docker |
| **Orchestration** | Kubernetes |
| **CI/CD** | GitHub Actions |
| **Monitoring** | Prometheus + Grafana |
| **Logging** | ELK Stack (Elasticsearch, Logstash, Kibana) |
| **Tracing** | Jaeger |
| **Secrets Management** | HashiCorp Vault / Kubernetes Secrets |

### Python Package Dependencies

```toml
# pyproject.toml
[tool.poetry.dependencies]
python = "^3.11"
python-telegram-bot = "^20.6"
openai = "^1.3"  # For LLM client
sqlalchemy = "^2.0"
asyncpg = "^0.29"  # PostgreSQL async driver
redis = "^5.0"
aioredis = "^2.0"
aiohttp = "^3.9"
pydantic = "^2.5"
pydantic-settings = "^2.1"
fastapi = "^0.104"
uvicorn = "^0.24"
celery = "^5.3"
python-multipart = "^0.0.6"
python-jose = "^3.3"  # JWT tokens
passlib = "^1.7"  # Password hashing
aiofiles = "^23.2"
beautifulsoup4 = "^4.12"
tiktoken = "^0.5"  # Token counting
prometheus-client = "^0.19"
structlog = "^23.2"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4"
pytest-asyncio = "^0.21"
pytest-cov = "^4.1"
pytest-mock = "^3.12"
black = "^23.11"
ruff = "^0.1"
mypy = "^1.7"
pre-commit = "^3.5"
ipython = "^8.17"
```

---

## API Specifications

### Bot Webhook API

```python
from fastapi import FastAPI, Request, HTTPException
from telegram import Update

app = FastAPI()

@app.post("/webhook/{token}")
async def webhook(token: str, request: Request):
    """Receive Telegram updates via webhook"""
    
    if token != bot_config.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    update_data = await request.json()
    update = Update.de_json(update_data, bot.application.bot)
    
    await bot.application.process_update(update)
    
    return {"ok": True}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "llm_status": await llm_service.health_check(),
        "db_status": await db_health_check(),
        "redis_status": await redis_health_check()
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return prometheus_client.generate_latest()
```

### Admin API

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin JWT token"""
    token = credentials.credentials
    # Verify JWT token
    if not is_valid_admin_token(token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication credentials"
        )
    return token

@app.get("/api/admin/stats", dependencies=[Depends(verify_admin)])
async def get_stats():
    """Get bot statistics"""
    return {
        "total_users": await get_user_count(),
        "active_sessions": await get_active_session_count(),
        "messages_today": await get_message_count_today(),
        "llm_calls_today": await get_llm_call_count_today(),
        "average_response_time": await get_avg_response_time(),
    }

@app.post("/api/admin/users/{user_id}/block", dependencies=[Depends(verify_admin)])
async def block_user(user_id: int):
    """Block a user"""
    await security_manager.block_user(user_id)
    return {"success": True}

@app.post("/api/admin/broadcast", dependencies=[Depends(verify_admin)])
async def broadcast_message(message: BroadcastRequest):
    """Send broadcast message to all users"""
    await bot.broadcast_message(message.text, message.target_users)
    return {"success": True, "sent_count": len(message.target_users)}
```

### MCP Plugin API

**Note:** The following MCP management API endpoints have been removed from the current implementation:

```python
# Removed endpoints (for historical reference):
# @app.get("/api/mcps") - List all registered MCPs
# @app.get("/api/mcps/{mcp_name}/tools") - Get tools from an MCP
# @app.post("/api/mcps/{mcp_name}/enable") - Enable/disable an MCP

# Current bot does not expose MCP management API
# MCPs are configured at startup and currently disabled (0 registered plugins)
```

---

## Testing Strategy

### Test Pyramid

```
                 /\
                /  \
               /E2E \
              /------\
             /        \
            /Integration\
           /------------\
          /              \
         /  Unit Tests    \
        /------------------\
```

### Unit Tests

```python
# tests/test_session_manager.py
import pytest
from bot.session import SessionManager, UserSession

@pytest.mark.asyncio
async def test_session_creation():
    """Test creating a new user session"""
    manager = SessionManager(db_mock, cache_mock)
    session = await manager.get_session(user_id=123)
    
    assert session.user_id == 123
    assert len(session.conversation_history) == 0
    assert session.active_mcps == []

@pytest.mark.asyncio
async def test_context_window():
    """Test context window management"""
    manager = SessionManager(db_mock, cache_mock)
    session = await manager.get_session(user_id=123)
    
    # Add many messages
    for i in range(100):
        await manager.update_context(123, Message(role="user", content=f"Message {i}"))
    
    # Get context window
    window = await manager.get_context_window(123, max_tokens=1000)
    
    assert len(window) < 100  # Should be truncated
    assert sum(len(m.content) for m in window) <= 1000
```

### Integration Tests

```python
# tests/integration/test_llm_mcp_integration.py
import pytest

@pytest.mark.asyncio
async def test_llm_with_file_mcp():
    """Test LLM using File System MCP"""
    
    # Setup
    fs_mcp = FileSystemMCP({"base_path": "/tmp/test"})
    await fs_mcp.initialize()
    
    llm = OllamaProvider(test_config)
    
    # Write test file
    await fs_mcp.execute_tool("write_file", {
        "file_path": "test.txt",
        "content": "Hello from MCP!"
    })
    
    # Ask LLM to read file
    messages = [
        {"role": "user", "content": "Read the file test.txt"}
    ]
    tools = await fs_mcp.get_tools()
    
    response = await llm.generate(messages, tools=tools)
    
    assert "Hello from MCP" in response or "tool_calls" in str(response)
```

### End-to-End Tests

```python
# tests/e2e/test_bot_workflow.py
import pytest
from telegram import Update

@pytest.mark.asyncio
async def test_complete_conversation():
    """Test complete user conversation flow"""
    
    # Simulate user sending message
    update = create_mock_update(user_id=123, text="Hello, bot!")
    
    # Process update
    await bot.application.process_update(update)
    
    # Check response was sent
    assert len(mock_telegram_api.sent_messages) == 1
    response = mock_telegram_api.sent_messages[0]
    assert response.chat_id == 123
    assert len(response.text) > 0

@pytest.mark.asyncio
async def test_tool_calling_workflow():
    """Test LLM calling MCP tools"""
    
    update = create_mock_update(
        user_id=123,
        text="Create a file called hello.txt with the content 'Hello World'"
    )
    
    await bot.application.process_update(update)
    
    # Verify file was created
    fs_mcp = bot.mcp_manager.mcps["FileSystemMCP"]
    content = await fs_mcp.execute_tool("read_file", {"file_path": "hello.txt"})
    assert content == "Hello World"
    
    # Verify response to user
    response = mock_telegram_api.sent_messages[-1]
    assert "created" in response.text.lower()
```

### Test Coverage Goals

- **Unit Tests**: >80% code coverage
- **Integration Tests**: All component interactions
- **E2E Tests**: Critical user workflows
- **Load Tests**: 1000+ concurrent users

---

## Monitoring & Observability

### Metrics Collection

```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
message_counter = Counter(
    'bot_messages_total',
    'Total messages processed',
    ['status', 'user_type']
)

llm_latency = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration',
    ['model', 'status']
)

active_sessions = Gauge(
    'bot_active_sessions',
    'Number of active user sessions'
)

mcp_calls = Counter(
    'mcp_tool_calls_total',
    'Total MCP tool calls',
    ['mcp_name', 'tool_name', 'status']
)

class MetricsMiddleware:
    """Collect metrics for all requests"""
    
    async def process_message(self, update: Update):
        """Process with metrics"""
        start_time = time.time()
        
        try:
            await self.handler(update)
            message_counter.labels(status='success', user_type='regular').inc()
        except Exception as e:
            message_counter.labels(status='error', user_type='regular').inc()
            raise
        finally:
            duration = time.time() - start_time
            llm_latency.labels(model='gpt-oss-20b', status='success').observe(duration)
```

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# Usage
logger.info(
    "message_processed",
    user_id=user_id,
    message_length=len(message),
    llm_tokens=token_count,
    response_time=duration,
    mcp_calls=mcp_call_count
)
```

### Alerting Rules

```yaml
# prometheus/alerts.yml
groups:
  - name: telegram_bot
    rules:
      - alert: HighErrorRate
        expr: rate(bot_messages_total{status="error"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          
      - alert: LLMSlowResponse
        expr: histogram_quantile(0.95, llm_request_duration_seconds) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "LLM response time is slow"
          
      - alert: DatabaseConnectionLost
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database connection lost"
```

### Grafana Dashboard

Key metrics to visualize:
- Messages per minute
- Active users/sessions
- LLM response time (p50, p95, p99)
- Error rate
- MCP tool usage
- Resource utilization (CPU, memory)
- Database query performance
- Cache hit rate

---

## Appendix

### A. Glossary

- **MCP**: Model Context Protocol - Framework for extending LLM capabilities (currently disabled)
- **LLM**: Large Language Model
- **Ollama**: LLM provider platform, currently using gpt-oss:120b-cloud model
- **Session**: User conversation context and state
- **Context Window**: Recent conversation history within token limits
- **Tool Calling**: LLM requesting execution of external functions
- **Rate Limiting**: Restriction on request frequency to prevent abuse

### B. References

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/)

### C. Configuration Examples

See `/config/` directory for:
- `config.example.yaml` - Main configuration template
- `mcps.example.yaml` - MCP configuration examples
- `docker-compose.yml` - Docker deployment configuration
- `kubernetes/` - Kubernetes manifests

### D. Contributing Guidelines

See `CONTRIBUTING.md` for:
- Code style guidelines
- Pull request process
- MCP development guide
- Testing requirements

---

## Conclusion

This design document provides a comprehensive blueprint for building a production-ready Telegram bot with LLM integration and MCP extensibility. The architecture emphasizes:

1. **Modularity**: Clean separation of concerns
2. **Extensibility**: Easy addition of new capabilities via MCPs
3. **Scalability**: Designed to handle thousands of users
4. **Maintainability**: Clear structure and documentation
5. **Reliability**: Error handling and fault tolerance

The next steps are:
1. Review and approve this design
2. Set up development environment
3. Begin Phase 1 implementation
4. Iterative development following the roadmap

This is a living document that will be updated as the project evolves and new requirements emerge.

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-22 | Design Team | Initial design document |

