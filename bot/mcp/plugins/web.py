"""Web Search and Fetch MCP Plugin"""

from typing import Dict, Any, List
import aiohttp
import asyncio
import structlog
import re
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
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
        
        # NOTE: For security reasons, in production you should restrict allowed domains
        # This allows all domains for development/testing purposes
        allow_all = config.get("allow_all_domains", False)
        
        if allow_all:
            self.allowed_domains = None  # None means all domains allowed
        else:
            # List of allowed domains for direct URL access
            default_allowed = {
                "wttr.in",
                "worldpublicholiday.com",
                "en.wikipedia.org",
                "www.wikipedia.org",
                "github.com",
                "raw.githubusercontent.com",
                "docs.python.org",
                "stackoverflow.com",
                "www.stackoverflow.com",
                "pypi.org",
                "www.pypi.org"
            }
            self.allowed_domains = set(config.get("allowed_domains", default_allowed))
    
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
        # Security check - only allow specific domains (if configured)
        if self.allowed_domains is not None:
            domain = urlparse(url).netloc
            if domain not in self.allowed_domains:
                raise ValueError(f"Direct URL access not allowed for domain: {domain}")
        
        # Log warning if all domains are allowed (security consideration)
        if self.allowed_domains is None:
            logger.warning("All domains are allowed - this is a security risk")

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
                            
                            # Clean and extract meaningful content
                            clean_content = self._extract_text_from_html(content)
                            
                            return {
                                "url": url,
                                "content": clean_content,
                                "content_type": response.headers.get('content-type', ''),
                                "status": response.status,
                                "success": True
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
            async with aiohttp.ClientSession() as session:
                # Use DuckDuckGo HTML search to avoid API issues
                url = "https://html.duckduckgo.com/html/"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Connection': 'keep-alive',
                }
                params = {'q': query}
                
                async with session.post(url, data=params, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"Search failed with status {response.status}")
                    
                    text = await response.text()
                    logger.debug(f"Got search response: {text[:500]}...")
                    
                    # Use BeautifulSoup for robust HTML parsing
                    soup = BeautifulSoup(text, 'lxml')
                    results = []
                    
                    for result in soup.find_all('div', class_='result'):
                        if len(results) >= top_n:
                            break
                        
                        title_elem = result.find('a', class_='result__a')
                        snippet_elem = result.find('a', class_='result__snippet')
                        url_elem = result.find('a', class_='result__url')
                        
                        if title_elem and snippet_elem and url_elem:
                            # Decode URL from DDG's redirect
                            raw_url = url_elem['href']
                            unquoted_url = unquote(raw_url)
                            
                            # Extract the actual URL from the 'uddg' parameter
                            final_url = unquoted_url[unquoted_url.find('uddg=')+5:] if 'uddg=' in unquoted_url else unquoted_url
                            
                            results.append({
                                'title': title_elem.text.strip(),
                                'snippet': snippet_elem.text.strip(),
                                'url': final_url
                            })
                    
                    return {
                        "results": results,
                        "total_results": len(results),
                        "success": True
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

    
    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract clean text content from HTML"""
        if not html_content:
            return ""
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Remove script and style elements
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up whitespace and formatting
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Truncate if very long to avoid overwhelming the model
            if len(clean_text) > 5000:
                clean_text = clean_text[:5000] + "\n\n[Content truncated...]"
            
            return clean_text
        except Exception as e:
            logger.warning(f"Failed to extract text from HTML: {e}")
            # Fallback to raw content if parsing fails
            return html_content[:1000] if len(html_content) > 1000 else html_content

    async def get_context(self, query: str) -> Dict[str, Any]:
        """Get context from the web - this is used when auto-gathering context"""
        # For web searches, we'll do a quick search and return the results
        if not query:
            return {"results": []}
        
        try:
            search_results = await self._search_web(query, top_n=3)  # Limit to 3 results for context
            return {
                "query": query,
                "success": True,
                **search_results
            }
        except Exception as e:
            logger.error(f"Failed to get web context: {str(e)}")
            return {
                "query": query,
                "error": str(e),
                "success": False,
                "results": []
            }