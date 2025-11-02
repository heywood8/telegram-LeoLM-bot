"""Database MCP Plugin"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
import structlog

from bot.mcp.base import BaseMCP

logger = structlog.get_logger()


class DatabaseMCP(BaseMCP):
    """MCP for database operations"""
    
    version = "1.0.0"
    description = "Provides database query and manipulation capabilities"
    
    async def initialize(self) -> bool:
        self.db_url = self.config.get("database_url")
        if not self.db_url:
            logger.warning("DatabaseMCP: No database_url provided")
            return False
        
        self.engine = create_async_engine(self.db_url, echo=False)
        logger.info(f"DatabaseMCP initialized with database")
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
        try:
            tables = await self._get_table_list()
            return {
                "available_tables": tables,
                "connection_status": "connected"
            }
        except Exception as e:
            return {
                "connection_status": "error",
                "error": str(e)
            }
    
    async def _execute_query(self, query: str) -> List[Dict]:
        """Execute SQL query (read-only)"""
        # Validate query is SELECT only
        query_stripped = query.strip().upper()
        if not query_stripped.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")
        
        # Check for dangerous keywords
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"]
        if any(keyword in query_stripped for keyword in dangerous_keywords):
            raise ValueError("Query contains forbidden keywords")
        
        async with self.engine.begin() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()
            
            if not rows:
                return []
            
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]
    
    async def _get_schema(self, table_name: Optional[str] = None) -> Dict:
        """Get schema information"""
        # This is a simplified version - real implementation would be database-specific
        async with self.engine.begin() as conn:
            if table_name:
                # Get columns for specific table (PostgreSQL-specific)
                query = text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                    ORDER BY ordinal_position
                """)
                result = await conn.execute(query, {"table_name": table_name})
                columns = [
                    {
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES"
                    }
                    for row in result.fetchall()
                ]
                return {"table": table_name, "columns": columns}
            else:
                tables = await self._get_table_list()
                return {"tables": tables}
    
    async def _get_table_list(self) -> List[str]:
        """Get list of tables"""
        async with self.engine.begin() as conn:
            # PostgreSQL-specific query
            query = text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            result = await conn.execute(query)
            return [row[0] for row in result.fetchall()]
    
    async def shutdown(self) -> None:
        """Cleanup resources"""
        if hasattr(self, 'engine'):
            await self.engine.dispose()
