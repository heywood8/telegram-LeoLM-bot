"""News MCP Plugin"""

from typing import Dict, Any, List
import feedparser
import asyncio
import structlog
from bot.mcp.base import BaseMCP

logger = structlog.get_logger()

class NewsMCP(BaseMCP):
    """News MCP plugin for fetching headlines from RSS feeds"""
    
    name = "news"
    description = "Fetch news headlines from various sources"
    version = "1.0.0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.enabled = True
        # Define a list of trusted news sources
        self.sources = {
            # General News
            #"google_news": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
            #"bbc": "http://feeds.bbci.co.uk/news/rss.xml",
            "the_guardian": "https://www.theguardian.com/world/rss",

            # News in Russia
            "rbc": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
            
            # Technology
            "wired": "https://www.wired.com/feed/rss",
            #"hacker_news": "https://news.ycombinator.com/rss",
        }
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get available tools"""
        return [
            {
                "function": {
                    "name": "news.get_headlines",
                    "description": "The primary tool for all news-related queries. Use it for general news ('what's happening in the world?') or for headlines from a specific source ('latest from BBC').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Optional: The specific news source to fetch from. If not provided, a default source will be used.",
                                "enum": list(self.sources.keys()),
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Number of headlines to return",
                                "default": 5,
                            },
                        },
                    },
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a tool"""
        if tool_name != "news.get_headlines":
            raise ValueError(f"Unknown tool: {tool_name}")
        
        source = parameters.get("source")
        limit = parameters.get("limit", 5)
        
        # If a specific source is provided, fetch from it
        if source:
            source = source.lower()
            if source not in self.sources:
                raise ValueError(f"Invalid news source. Available sources: {', '.join(self.sources.keys())}")
            return await self._get_headlines(source, limit)
        
        # If no source is provided, fetch from all sources and combine
        return await self._get_all_headlines(limit)
    
    async def _get_all_headlines(self, limit: int) -> Dict[str, Any]:
        """Fetch headlines from all sources and combine them"""
        all_headlines = []
        tasks = [self._get_headlines(source, limit) for source in self.sources.keys()]
        results = await asyncio.gather(*tasks)
        
        for result in results:
            if result.get("success"):
                all_headlines.extend(result.get("headlines", []))
        
        # Sort by published date, newest first (requires parsing dates)
        # Note: This is a best-effort sort as date formats can vary.
        # For simplicity, we'll skip sorting for now.
        
        return {
            "source": "all",
            "headlines": all_headlines[:limit * len(self.sources)], # Limit total headlines
            "success": True,
        }
    
    async def _get_headlines(self, source: str, limit: int) -> Dict[str, Any]:
        """Fetch and parse RSS feed"""
        feed_url = self.sources[source]
        
        try:
            # feedparser is synchronous, so we run it in an executor
            loop = asyncio.get_running_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
            
            if feed.bozo:
                raise Exception(f"Failed to parse feed: {feed.bozo_exception}")
            
            headlines = []
            for entry in feed.entries[:limit]:
                headlines.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.summary,
                    "published": entry.published,
                })
            
            return {
                "source": source,
                "headlines": headlines,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Failed to fetch news from {source}", exc_info=e)
            return {"error": str(e), "success": False}

    async def initialize(self) -> None:
        """Initialize the plugin"""
        pass
    
    async def shutdown(self) -> None:
        """Shutdown the plugin"""
        pass

    async def get_context(self, query: str) -> Dict[str, Any]:
        """Get context for a query (e.g., latest headlines)"""
        # For context, we'll just get the top 3 headlines from a default source
        return await self._get_headlines("google_news", 3)
