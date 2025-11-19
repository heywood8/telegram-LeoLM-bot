"""Configuration management using Pydantic Settings"""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramConfig(BaseSettings):
    """Telegram bot configuration"""
    
    bot_token: str = Field(..., validation_alias="TELEGRAM_BOT_TOKEN")
    webhook_url: Optional[str] = Field(None, validation_alias="TELEGRAM_WEBHOOK_URL")
    webhook_secret: Optional[str] = Field(None, validation_alias="TELEGRAM_WEBHOOK_SECRET")


class LLMConfig(BaseSettings):
    """LLM configuration"""

    provider: str = Field("ollama", validation_alias="LLM_PROVIDER")
    base_url: str = Field("https://ollama.com/v1", validation_alias="LLM_BASE_URL")
    model_name: str = Field("gpt-oss:120b-cloud", validation_alias="LLM_MODEL_NAME")
    api_key: Optional[str] = Field(None, validation_alias="LLM_API_KEY")
    temperature: float = Field(0.7, validation_alias="LLM_TEMPERATURE")
    max_tokens: int = Field(2048, validation_alias="LLM_MAX_TOKENS")
    timeout: int = Field(60, validation_alias="LLM_TIMEOUT")
    request_timeout: int = Field(30, validation_alias="LLM_REQUEST_TIMEOUT")
    retry_attempts: int = Field(3, validation_alias="LLM_RETRY_ATTEMPTS")
    retry_min_wait: int = Field(2, validation_alias="LLM_RETRY_MIN_WAIT")
    retry_max_wait: int = Field(10, validation_alias="LLM_RETRY_MAX_WAIT")
    circuit_breaker_failures: int = Field(5, validation_alias="LLM_CIRCUIT_BREAKER_FAILURES")
    circuit_breaker_timeout: int = Field(60, validation_alias="LLM_CIRCUIT_BREAKER_TIMEOUT")


class DatabaseConfig(BaseSettings):
    """Database configuration"""
    
    url: str = Field(..., validation_alias="DATABASE_URL")


class RedisConfig(BaseSettings):
    """Redis configuration"""
    
    url: str = Field("redis://localhost:6379/0", validation_alias="REDIS_URL")


class MCPConfig(BaseSettings):
    """MCP framework configuration
    
    NOTE: All MCPs are currently disabled in bot/main.py (0 registered plugins).
    These config values are kept for future use or external MCP integration.
    """
    
    filesystem_enabled: bool = Field(False, validation_alias="MCP_FILESYSTEM_ENABLED")
    filesystem_base_path: str = Field("/tmp/bot_workspace", validation_alias="MCP_FILESYSTEM_BASE_PATH")
    
    database_enabled: bool = Field(False, validation_alias="MCP_DATABASE_ENABLED")
    database_url: Optional[str] = Field(None, validation_alias="MCP_DATABASE_URL")
    
    # Built-in WebSearch MCP removed - use external MCP service instead
    websearch_enabled: bool = Field(False, validation_alias="MCP_WEBSEARCH_ENABLED")
    websearch_url: Optional[str] = Field(None, validation_alias="MCP_WEBSEARCH_URL")
    websearch_api_key: Optional[str] = Field(None, validation_alias="MCP_WEBSEARCH_API_KEY")
    websearch_search_engine: str = Field("duckduckgo", validation_alias="MCP_WEBSEARCH_SEARCH_ENGINE")


class SecurityConfig(BaseSettings):
    """Security configuration"""
    
    admin_user_ids: str = Field("", validation_alias="ADMIN_USER_IDS")
    secret_key: str = Field(..., validation_alias="SECRET_KEY")
    jwt_algorithm: str = Field("HS256", validation_alias="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(24, validation_alias="JWT_EXPIRATION_HOURS")
    
    @property
    def admin_ids(self) -> List[int]:
        """Parse admin user IDs"""
        if not self.admin_user_ids:
            return []
        return [int(uid.strip()) for uid in self.admin_user_ids.split(",") if uid.strip()]


class RateLimitConfig(BaseSettings):
    """Rate limiting configuration"""
    
    user_requests: int = Field(20, validation_alias="RATE_LIMIT_USER_REQUESTS")
    user_window: int = Field(60, validation_alias="RATE_LIMIT_USER_WINDOW")
    global_requests: int = Field(100, validation_alias="RATE_LIMIT_GLOBAL_REQUESTS")
    global_window: int = Field(60, validation_alias="RATE_LIMIT_GLOBAL_WINDOW")


class ResourceLimits(BaseSettings):
    """Resource limits configuration"""

    max_message_length: int = Field(4096, validation_alias="MAX_MESSAGE_LENGTH")
    max_history_messages: int = Field(50, validation_alias="MAX_HISTORY_MESSAGES")
    max_context_tokens: int = Field(8000, validation_alias="MAX_CONTEXT_TOKENS")
    max_file_size: int = Field(20 * 1024 * 1024, validation_alias="MAX_FILE_SIZE")
    max_concurrent_llm_calls: int = Field(10, validation_alias="MAX_CONCURRENT_LLM_CALLS")
    max_mcp_execution_time: int = Field(30, validation_alias="MAX_MCP_EXECUTION_TIME")
    tool_execution_timeout: int = Field(15, validation_alias="TOOL_EXECUTION_TIMEOUT")
    tool_retry_attempts: int = Field(2, validation_alias="TOOL_RETRY_ATTEMPTS")


class AppConfig(BaseSettings):
    """Application configuration"""
    
    host: str = Field("0.0.0.0", validation_alias="APP_HOST")
    port: int = Field(8000, validation_alias="APP_PORT")
    use_webhook: bool = Field(False, validation_alias="USE_WEBHOOK")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field("json", validation_alias="LOG_FORMAT")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    # When running under docker-compose we prefer the compose-specific env file.
    # This will be overridden by actual environment variables when present.
    model_config = SettingsConfigDict(env_file=".env.docker-compose", env_file_encoding="utf-8", extra="ignore")


class Config:
    """Main configuration container"""
    
    def __init__(self) -> None:
        self.telegram = TelegramConfig()
        self.llm = LLMConfig()
        self.database = DatabaseConfig()
        self.redis = RedisConfig()
        self.mcp = MCPConfig()
        self.security = SecurityConfig()
        self.rate_limit = RateLimitConfig()
        self.resource_limits = ResourceLimits()
        self.app = AppConfig()


# Global configuration instance
config = Config()
