"""Main application entry point"""

import asyncio
import signal
import sys
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import structlog

from bot.config import config
from bot.database import init_db, close_db
from bot.session import SessionManager
from bot.llm.provider import OllamaProvider
from bot.llm.service import LLMService
from bot.mcp.manager import MCPManager
from bot.mcp.plugins import FileSystemMCP, DatabaseMCP
from bot.mcp.plugins.web import WebMCP
from bot.rate_limiter import RateLimiter
from bot.handlers import BotHandlers
from bot.utils import setup_logging

logger = structlog.get_logger()


class TelegramBot:
    """Main bot application"""
    
    def __init__(self):
        self.application: Application = None
        self.mcp_manager: MCPManager = None
        self.rate_limiter: RateLimiter = None
        self.llm_service: LLMService = None
    
    async def initialize(self) -> None:
        """Initialize bot components"""
        
        logger.info("Initializing Telegram bot...")
        
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Initialize LLM with Ollama provider
        llm_provider = OllamaProvider()

        # Log resolved LLM configuration for easier debugging (helps track env overrides)
        logger.info(
            "LLM configuration",
            provider=config.llm.provider,
            model=config.llm.model_name,
            base_url=config.llm.base_url,
        )
        self.llm_service = LLMService(llm_provider)
        logger.info(f"LLM service initialized: {config.llm.model_name}")
        
        # Initialize MCP Manager
        self.mcp_manager = MCPManager()
        
        # Register MCP plugins
        if config.mcp.filesystem_enabled:
            fs_mcp = FileSystemMCP({"base_path": config.mcp.filesystem_base_path})
            await self.mcp_manager.register_mcp(fs_mcp)
        
        if config.mcp.database_enabled and config.mcp.database_url:
            db_mcp = DatabaseMCP({"database_url": config.mcp.database_url})
            await self.mcp_manager.register_mcp(db_mcp)
            
        # Register web tools (both search and URL fetch)
        web_mcp = WebMCP({
            "api_key": config.mcp.websearch_api_key,
            "search_engine": config.mcp.websearch_search_engine
        })
        await self.mcp_manager.register_mcp(web_mcp)
        
        logger.info(f"Registered {len(self.mcp_manager.mcps)} MCP plugins")
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter()
        logger.info("Rate limiter initialized")
        
        # Build Telegram application
        self.application = (
            Application.builder()
            .token(config.telegram.bot_token)
            .build()
        )
        
        # Create handlers
        from bot.database import async_session_factory
        async with async_session_factory() as db:
            session_manager = SessionManager(db)
            bot_handlers = BotHandlers(
                session_manager=session_manager,
                llm_service=self.llm_service,
                mcp_manager=self.mcp_manager,
                rate_limiter=self.rate_limiter
            )
            
            # Register handlers
            self.application.add_handler(CommandHandler("start", bot_handlers.start_command))
            self.application.add_handler(CommandHandler("help", bot_handlers.help_command))
            self.application.add_handler(CommandHandler("reset", bot_handlers.reset_command))
            self.application.add_handler(CommandHandler("get_system_prompt", bot_handlers.get_system_prompt_command))
            self.application.add_handler(CommandHandler("set_system_prompt", bot_handlers.set_system_prompt_command))
            # Handle messages in private chats, groups, and supergroups
            self.application.add_handler(
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
                    bot_handlers.handle_message
                )
            )
            self.application.add_error_handler(bot_handlers.error_handler)
        
        logger.info("Bot handlers registered")
    
    async def start(self) -> None:
        """Start the bot"""
        
        await self.initialize()
        
        logger.info("Starting bot...")
        
        if config.app.use_webhook:
            # Webhook mode
            webhook_url = config.telegram.webhook_url
            logger.info(f"Starting webhook at {webhook_url}")
            
            await self.application.bot.set_webhook(
                url=f"{webhook_url}/{config.telegram.webhook_secret}",
                allowed_updates=["message", "callback_query"]
            )
            
            # Start webhook server
            await self.application.run_webhook(
                listen=config.app.host,
                port=config.app.port,
                url_path=config.telegram.webhook_secret,
                webhook_url=f"{webhook_url}/{config.telegram.webhook_secret}",
            )
        else:
            # Polling mode
            logger.info("Starting polling mode")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
            
            logger.info("Bot is running! Press Ctrl+C to stop.")
            
            # Keep running
            stop_event = asyncio.Event()
            
            def signal_handler(sig, frame):
                logger.info("Received shutdown signal")
                stop_event.set()
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            await stop_event.wait()
    
    async def shutdown(self) -> None:
        """Shutdown bot gracefully"""
        
        logger.info("Shutting down bot...")
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
        
        if self.mcp_manager:
            await self.mcp_manager.shutdown_all()
        
        if self.rate_limiter:
            await self.rate_limiter.close()
        
        await close_db()
        
        logger.info("Bot shutdown complete")


async def main() -> None:
    """Main entry point"""
    
    # Setup logging
    setup_logging(
        log_level=config.app.log_level,
        log_format=config.app.log_format
    )
    
    logger.info(f"Starting Telegram LLM Bot v{__import__('bot').__version__}")
    
    bot = TelegramBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
