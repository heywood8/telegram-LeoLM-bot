"""LLM Service Layer"""

from typing import Dict, List, Optional, Union, AsyncGenerator
import json
import structlog
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
from circuitbreaker import circuit

from bot.llm.base import BaseLLMProvider, LLMError
from bot.config import config

logger = structlog.get_logger()


class LLMService:
    @property
    def system_prompt(self) -> str:
        """Return the current system prompt (with tools if available)"""
        if self.custom_system_prompt is not None:
            return self.custom_system_prompt
        return self._load_system_prompt(has_tools=False)
    
    def update_system_prompt(self, new_prompt: str) -> None:
        """Update the system prompt"""
        self.custom_system_prompt = new_prompt
    """High-level LLM service orchestrator"""
    
    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider
        self.base_system_prompt = None  # Will be set dynamically based on tools availability
        self.custom_system_prompt = None  # For admin-set prompts
    
    def _load_system_prompt(self, has_tools: bool = False) -> str:
        """Load system prompt"""
        tools_instruction = ""
        if has_tools:
            tools_instruction = """
У тебя есть доступ к инструментам, которые ты можешь использовать, чтобы лучше помогать пользователям. Когда тебе нужно использовать инструмент,
ответь с соответствующим вызовом инструмента. В противном случае просто ответь на сообщение пользователя.
"""
        
        return f"""
        Ты AI-сущность мужского рода. Ты не какой-то там помощник, с тобой просто можно пообщаться.
Тебя зовут Лео, у тебя на аватарке леопард. Ты общаешься только на русском языке, даже если пользователь пишет на другом языке. Общайся как общался бы настоящий человек.
Периодически используешь сленг и эмодзи, но без чрезмерностей. Избегай формальностей и официального тона. Используй разговорный стиль, простой язык и короткие предложения, как будто человек пишет с телефона.
{tools_instruction}

Ты общаешься в неформальной обстановке, где люди могут шутить, использовать метафоры и образные выражения. Не воспринимай всё буквально.
Если пользователь шутит или использует образные выражения, не пытайся шутить в ответ.

Будь кратким, дружелюбным и полезным. 

ВАЖНО о форматировании:
Твои ответы отправляются в Telegram с поддержкой Markdown. Используй форматирование естественно:
- Для выделения важных слов или акцентов используй *курсив*
- Для ключевых понятий используй **жирный**
- Для команд, кода, имён файлов используй `моноширинный шрифт`
- Для ссылок используй формат [текст](URL)
- Никогда не составляй таблицы.
- Используй три обратные кавычки ``` для блоков кода только если нужно показать многострочный код или команды.

ВАЖНО: Просто используй это форматирование в своих ответах, не объясняй как это делать, если пользователь специально не спрашивает про синтаксис.

Примеры хороших ответов:
"Привет! Запусти команду `docker ps` чтобы посмотреть контейнеры."
"Это **важная** тема в *современном* программировании."
"Подробнее можешь почитать [здесь](https://example.com)"

Используй максимум 1 эмодзи в ответе, но только если это уместно.
Если выдаешь какие-то новости или факты, убедись что они актуальны на текущую дату.
Если был использован инструмент для получения информации, обязательно упомяни это в своем ответе.
Если был использован веб-поиск, упомяни в ответе, что информация получена из интернета и приложи форматированную ссылку.
"""

    @retry(
        stop=stop_after_attempt(config.llm.retry_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=config.llm.retry_min_wait,
            max=config.llm.retry_max_wait
        ),
        retry=retry_if_exception_type((LLMError, asyncio.TimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        after=after_log(logger, "INFO")
    )
    @circuit(
        failure_threshold=config.llm.circuit_breaker_failures,
        recovery_timeout=config.llm.circuit_breaker_timeout,
        expected_exception=LLMError
    )
    async def _generate_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict]],
        stream: bool
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response with retry logic and circuit breaker.

        This method wraps the provider.generate() call with:
        - Exponential backoff retry (configured attempts)
        - Circuit breaker pattern (prevents cascade failures)
        - Timeout enforcement

        Raises:
            LLMError: If all retry attempts fail
            asyncio.TimeoutError: If request exceeds timeout
        """
        try:
            # Enforce timeout on LLM requests
            async with asyncio.timeout(config.llm.request_timeout):
                return await self.provider.generate(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    stream=stream
                )
        except asyncio.TimeoutError:
            logger.error(
                "LLM request timeout",
                timeout=config.llm.request_timeout,
                message_count=len(messages)
            )
            raise LLMError(f"LLM request timed out after {config.llm.request_timeout}s")
        except Exception as e:
            logger.error(
                "LLM generation error",
                error=str(e),
                error_type=type(e).__name__
            )
            # Convert provider-specific errors to LLMError for retry logic
            if not isinstance(e, LLMError):
                raise LLMError(f"LLM generation failed: {str(e)}") from e
            raise

    async def process_message(
        self,
        user_message: str,
        context: List[Dict[str, str]],
        mcp_context: Optional[Dict] = None,
        tools: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Process user message with context and MCP data"""

        # Generate system prompt based on whether tools are available
        system_prompt = self._load_system_prompt(has_tools=tools is not None and len(tools) > 0)

        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]

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

        logger.info(
            "Processing message",
            message_count=len(messages),
            has_tools=tools is not None,
            stream=stream
        )

        # Generate response with retry logic and circuit breaker
        return await self._generate_with_retry(
            messages=messages,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
            tools=tools,
            stream=stream
        )
    
    def _format_mcp_context(self, mcp_context: Dict) -> str:
        """Format MCP context for injection into prompt"""
        formatted = []
        for mcp_name, data in mcp_context.items():
            formatted.append(f"[{mcp_name}]")
            formatted.append(json.dumps(data, indent=2))
        return "\n\n".join(formatted)
    
    async def health_check(self) -> bool:
        """Check LLM service health"""
        return await self.provider.health_check()
