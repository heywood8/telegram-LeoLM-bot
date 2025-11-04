"""Web Search and Fetch MCP Plugin"""

from typing import Dict, Any, List
import aiohttp
import asyncio
import structlog
import re
from urllib.parse import urlparse
from bot.mcp.base import BaseMCP

logger = structlog.get_logger()

class WebMCP(BaseMCP):
    """Web Search and Fetch MCP plugin"""
    
    name = "web"
    description = "Web search and URL fetch capabilities"
    version = "1.0.0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.search_engine = config.get("search_engine", "duckduckgo")
        self.enabled = True
        # List of allowed domains for direct URL access
        self.allowed_domains = {"wttr.in"}  # Add more trusted domains as needed
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get available tools"""
        return [
            {
                "function": {
                    "name": "web.run",  # Match the name the LLM is trying to use
                    "description": "Fetch content from a URL or search the web",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "URL to fetch or search query"
                            },
                            "source": {
                                "type": "string",
                                "description": "Source type: 'url' for direct URL access or 'news' for web search",
                                "enum": ["url", "news"],
                                "default": "url"
                            },
                            "top_n": {
                                "type": "integer",
                                "description": "Number of search results (for news source)",
                                "default": 5
                            }
                        },
                        "required": ["id"]
                    }
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a tool"""
        if tool_name != "web.run":
            raise ValueError(f"Unknown tool: {tool_name}")
        
        url_or_query = parameters.get("id", "")
        source_type = parameters.get("source", "url")
        top_n = parameters.get("top_n", 5)
        
        if not url_or_query:
            raise ValueError("URL or query is required")
        
        # If it looks like a URL and source type is url, fetch directly
        if source_type == "url" and (url_or_query.startswith("http://") or url_or_query.startswith("https://")):
            return await self._fetch_url(url_or_query)
        else:
            # Otherwise treat as a search query
            return await self._search_web(url_or_query, top_n)
    
    async def _fetch_url(self, url: str) -> Dict[str, Any]:
        """Fetch content from a URL with retries and proper error handling"""
        # Security check - only allow specific domains
        domain = urlparse(url).netloc
        if domain not in self.allowed_domains:
            raise ValueError(f"Direct URL access not allowed for domain: {domain}")

        max_retries = 3
        retry_delay = 1  # seconds
        last_error = None
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            return {
                                "url": url,
                                "content": content.strip(),
                                "content_type": response.headers.get('content-type', ''),
                                "status": response.status
                            }
                        elif response.status == 429:  # Too Many Requests
                            last_error = f"Rate limited (status 429)"
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay * (attempt + 1))
                                continue
                        else:
                            last_error = f"HTTP request failed with status {response.status}"
                            raise Exception(last_error)
                            
            except asyncio.TimeoutError:
                last_error = "Request timed out"
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                break
        
        logger.error(f"URL fetch failed after {max_retries} attempts: {last_error}")
        raise Exception(f"Failed to fetch URL: {last_error}")
    
    async def _search_web(self, query: str, top_n: int) -> Dict[str, Any]:
        """Search the web using DuckDuckGo Lite"""
        try:
            if "weather" in query.lower():
                # For weather queries, redirect to wttr.in
                location = query.lower().replace("weather", "").strip()
                return await self._fetch_url(f"https://wttr.in/{location}?format=3")

            async with aiohttp.ClientSession() as session:
                # Use DuckDuckGo Lite HTML search
                url = "https://lite.duckduckgo.com/lite"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                params = {
                    'q': query,
                    'kl': 'us-en'  # language/region
                }
                
                async with session.post(url, data=params, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"Search failed with status {response.status}")
                    
                    text = await response.text()
                    
                    # Extract search results using basic string parsing
                    results = []
                    lines = text.split('\n')
                    current_result = {}
                    
                    for line in lines:
                        if '<a class="result-link"' in line:
                            if current_result and len(results) < top_n:
                                results.append(current_result)
                            current_result = {}
                            # Extract URL and title
                            url_start = line.find('href="') + 6
                            url_end = line.find('"', url_start)
                            current_result['url'] = line[url_start:url_end]
                            # Extract title
                            title_start = line.find('>', url_end) + 1
                            title_end = line.find('</a>', title_start)
                            current_result['title'] = line[title_start:title_end].strip()
                        elif '<td class="result-snippet"' in line:
                            # Extract snippet
                            snippet_start = line.find('>') + 1
                            snippet_end = line.find('</td>', snippet_start)
                            current_result['snippet'] = line[snippet_start:snippet_end].strip()
                    
                    # Add the last result if we have one
                    if current_result and len(results) < top_n:
                        results.append(current_result)
                    
                    return {
                        "results": results,
                        "total_results": len(results)
                    }
                    
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            raise
    
    async def initialize(self) -> None:
        """Initialize the plugin"""
        # Nothing to initialize
        pass
    
    async def shutdown(self) -> None:
        """Shutdown the plugin"""
        # Nothing to clean up
        pass

    async def get_context(self, query: str) -> Dict[str, Any]:
        """Get context from the web - this is used when auto-gathering context"""
        # For web searches, we'll do a quick search and return the results
        if not query:
            return {"results": []}
        
        try:
            search_results = await self._search_web(query, top_n=3)  # Limit to 3 results for context
            return {
                "query": query,
                **search_results
            }
        except Exception as e:
            logger.error(f"Failed to get web context: {str(e)}")
            return {
                "query": query,
                "error": str(e),
                "results": []
            }