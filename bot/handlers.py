# -*- coding: utf-8 -*-
"""Telegram bot handlers"""

from telegram import Update
from telegram.ext import ContextTypes
import structlog
import json

from bot.session import SessionManager
import re
from bot.llm.service import LLMService
from bot.mcp.manager import MCPManager
from bot.rate_limiter import RateLimiter
from bot.config import config

logger = structlog.get_logger()


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    # Characters that need to be escaped: _ * [ ] ( ) ~ ` > # + - = | { } . !
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)


class BotHandlers:
    """Telegram bot message handlers"""
    
    def __init__(
        self,
        session_manager: SessionManager,
        llm_service: LLMService,
        mcp_manager: MCPManager,
        rate_limiter: RateLimiter
    ):
        self.session_manager = session_manager
        self.llm_service = llm_service
        self.mcp_manager = mcp_manager
        self.rate_limiter = rate_limiter
        self._waiting_for_prompt = {}
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user = update.effective_user
        welcome_message = (
            "👋 Привет! Я — бот с поддержкой AI. Я могу помочь вам с различными задачами и ответить на ваши вопросы.\n\n"
            "Используйте /help чтобы увидеть список доступных команд."
        )
        
        # Log the start command
        logger.info(
            "User started bot",
            first_name=getattr(user, 'first_name', None),
            last_name=getattr(user, 'last_name', None),
            username=getattr(user, 'username', None),
        )
        
        await update.message.reply_text(welcome_message)

    async def set_system_prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /set_system_prompt command for admins"""
        user = update.effective_user
        chat_id = update.message.chat.id
        
        # Check admin
        if user.id not in config.security.admin_ids:
            await update.message.reply_text("❌ Эта команда доступна только администраторам.")
            logger.info("Non-admin tried to set system prompt", user_id=user.id, chat_id=chat_id)
            return
        
        # Mark user as waiting for prompt
        self._waiting_for_prompt[chat_id] = user.id
        
        await update.message.reply_text(
            "Пожалуйста, отправьте новый системный промпт следующим сообщением.\n"
            "Для отмены используйте команду /cancel"
        )
        logger.info("Admin requested to set system prompt", user_id=user.id, chat_id=chat_id)

    async def get_system_prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /get_system_prompt command for admins"""
        user = update.effective_user
        chat_id = update.message.chat.id
        
        # Check admin
        admin_ids = config.security.admin_ids
        if user.id not in admin_ids:
            await update.message.reply_text("❌ Эта команда доступна только администраторам.")
            logger.info("Non-admin tried to access system prompt", user_id=user.id, chat_id=chat_id)
            return
        
        # Get current system prompt from LLMService
        try:
            system_prompt = self.llm_service.system_prompt
            if not system_prompt:
                system_prompt = "Системный промпт не установлен."
            
            # Format the response in a readable way
            response = "Текущий системный промпт:\n\n```\n" + system_prompt + "\n```"
            
            await update.message.reply_text(response, parse_mode="Markdown")
            logger.info("Admin viewed system prompt", user_id=user.id, chat_id=chat_id)
        except Exception as e:
            logger.error(f"Failed to get system prompt: {e}", exc_info=True)
            await update.message.reply_text("❌ Не удалось получить системный промпт.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        user = update.effective_user
        admin_ids = config.security.admin_ids if hasattr(config.security, 'admin_ids') else []
        is_admin = user.id in admin_ids
        
        help_text = "*Bot Commands*\n\n"
        help_text += "/start - Start the bot\n"
        help_text += "/help - Show this help\n"
        help_text += "/reset - Clear conversation history\n"
        help_text += "/settings - Manage preferences\n"
        
        if is_admin:
            help_text += "/get_system_prompt - Show current system prompt\n"
            help_text += "/set_system_prompt - Set new system prompt\n"
            
        help_text += "\nJust send me a message to get started!"
        
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reset command"""
        user = update.effective_user
        chat_id = update.message.chat.id
        
        # Get session (use chat_id so it resets the shared chat context)
        from bot.database import async_session_factory
        async with async_session_factory() as db:
            session_manager = SessionManager(db)
            user_session = await session_manager.get_session(chat_id, user.id, telegram_user=user)
            await session_manager.clear_session(user_session.session_id)
            await db.commit()
        
        # Different message for group vs private chats
        if update.message.chat.type in ["group", "supergroup"]:
            await update.message.reply_text("✅ История общего чата очищена!")
        else:
            await update.message.reply_text("✅ История разговора очищена!")
        
        logger.info(
            "User reset conversation",
            first_name=getattr(user, 'first_name', None),
            last_name=getattr(user, 'last_name', None),
            username=getattr(user, 'username', None),
            chat_id=chat_id,
            chat_type=update.message.chat.type,
        )
    

        
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular messages"""
        user = update.effective_user
        message = update.message
        message_text = message.text
        chat_id = message.chat.id

        # Check if this is a system prompt update from an admin
        if chat_id in self._waiting_for_prompt:
            if self._waiting_for_prompt[chat_id] == user.id:
                # Remove the waiting state
                del self._waiting_for_prompt[chat_id]
                
                if message_text.lower() == '/cancel':
                    await message.reply_text("❌ Установка системного промпта отменена.")
                    return
                
                try:
                    # Store the new prompt in database
                    from bot.database import async_session_factory
                    from bot.models import SystemPrompt, User
                    from sqlalchemy import select
                    
                    async with async_session_factory() as db:
                        # Get or create user record
                        result = await db.execute(select(User).where(User.telegram_id == user.id))
                        db_user = result.scalar_one_or_none()
                        if not db_user:
                            db_user = User(
                                telegram_id=user.id,
                                username=user.username,
                                first_name=user.first_name,
                                last_name=user.last_name,
                                is_admin=True
                            )
                            db.add(db_user)
                            await db.flush()
                        
                        # Import text for raw SQL
                        from sqlalchemy import text
                        
                        # Deactivate old prompts
                        await db.execute(
                            text("UPDATE system_prompts SET is_active = false WHERE is_active = true")
                        )
                        
                        # Create new prompt
                        new_prompt = SystemPrompt(
                            prompt=message_text,
                            set_by_user_id=db_user.id,
                            is_active=True
                        )
                        db.add(new_prompt)
                        await db.commit()
                    
                    # Update the LLM service
                    self.llm_service.update_system_prompt(message_text)
                    
                    await message.reply_text("✅ Системный промпт успешно обновлен!")
                    logger.info(
                        "System prompt updated",
                        user_id=user.id,
                        chat_id=chat_id
                    )
                    return
                except Exception as e:
                    logger.error(f"Failed to update system prompt: {e}", exc_info=True)
                    await message.reply_text("❌ Не удалось обновить системный промпт.")
                    return

        # Strip leading assistant role markers that some providers include in the
        # incoming message (e.g. "[assistant] Hello"). Keep a short preview
        # for logging but avoid storing full user text in logs.
        try:
            message_text = re.sub(r'^\s*\[assistant\]\s*', '', message_text or '', flags=re.IGNORECASE)
        except Exception:
            # Be tolerant of unexpected message shapes
            message_text = message_text or ''

        # Helper to determine whether bot is addressed in a group context.
        def _is_addressed_in_group(msg_text: str) -> tuple[bool, str]:
            """Return (is_addressed, cleaned_text) for group messages.

            Conditions:
            1. Explicit @username mention (entity type mention or raw text)
            2. Reply to bot's message
            3. Starts with bot's first name (common pattern) e.g. "BotName, help" or "BotName: help"
            """
            bot_username = context.bot.username if context.bot else None
            bot_first_name = context.bot.first_name if getattr(context.bot, 'first_name', None) else None
            if not bot_username:
                return False, msg_text

            lowered = msg_text.lower().strip()
            cleaned = msg_text
            addressed = False

            # Entities based mention (robust for Telegram official mentions)
            if message.entities:
                for entity in message.entities:
                    try:
                        if entity.type in ("mention", "text_mention"):
                            mention_text = msg_text[entity.offset:entity.offset + entity.length]
                            if mention_text.lower() == f"@{bot_username.lower()}":
                                addressed = True
                                cleaned = cleaned.replace(mention_text, "", 1).strip()
                                break
                    except Exception:
                        continue

            # Raw text fallback if user typed @BotName but Telegram didn't create entity
            if not addressed and f"@{bot_username.lower()}" in lowered:
                addressed = True
                idx = lowered.find(f"@{bot_username.lower()}")
                end_idx = idx + len(bot_username) + 1
                cleaned = (msg_text[:idx] + msg_text[end_idx:]).strip()

            # First-name prefix pattern ("BotName, help" or "BotName: help")
            if not addressed and bot_first_name:
                for sep in [":", ",", "-", "—"]:
                    prefix = f"{bot_first_name}{sep}"
                    if lowered.startswith(prefix.lower()):
                        addressed = True
                        cleaned = msg_text[len(prefix):].strip()
                        break

            # Reply check
            if not addressed and message.reply_to_message and message.reply_to_message.from_user and context.bot:
                if message.reply_to_message.from_user.id == context.bot.id:
                    addressed = True

            return addressed, cleaned if cleaned else msg_text
        
        # In group chats, only respond if bot is mentioned or message is a reply to bot
        if message.chat.type in ["group", "supergroup"]:
            is_addressed, cleaned_text = _is_addressed_in_group(message_text)
            if not is_addressed:
                return
            message_text = cleaned_text
        
        # Check rate limit
        allowed, retry_after = await self.rate_limiter.check_limit(user.id)
        if not allowed:
            await update.message.reply_text(
                f"⏱️ Rate limit exceeded. Please try again in {retry_after} seconds."
            )
            return
        
        # Consume rate limit token
        await self.rate_limiter.consume_token(user.id)
        
        # Send typing indicator (network calls may fail; don't let them crash the handler)
        try:
            await update.message.chat.send_action("typing")
        except Exception as e:
            # NetworkError (httpx.ConnectError) can happen if Telegram API is unreachable.
            # Log and continue — we'll still attempt to process the message.
            logger.warning("Failed to send typing action", exc_info=e)
        
        try:
            # Get session and context
            from bot.database import async_session_factory
            async with async_session_factory() as db:
                session_manager = SessionManager(db)
                # Use chat_id for session so context is shared across all users in the chat
                chat_id = message.chat.id
                user_session = await session_manager.get_session(chat_id, user.id, telegram_user=user)
                
                # Save user message first
                await session_manager.update_context(
                    session_id=user_session.session_id,
                    role="user",
                    content=message_text,
                    metadata={"chat_type": message.chat.type}
                )
                # Make sure the user message is committed
                await db.commit()

                # Get conversation context
                context_messages = await session_manager.get_context_window(
                    user_session.session_id
                )
                
                # Retrieve MCP tools for automatic tool calling. If the underlying
                # model or API rejects the tools parameter we'll fall back gracefully.
                try:
                    tools = await self.mcp_manager.get_all_tools()
                    if not tools:
                        tools = None
                        logger.debug("No MCP tools available")
                    else:
                        logger.info(f"Retrieved {len(tools)} MCP tools", tool_names=[t.get('function', {}).get('name') for t in tools])
                except Exception as e:
                    tools = None
                    logger.warning(f"Failed to retrieve MCP tools: {e}", exc_info=True)

                # Log incoming message (truncated) for debugging/audit.
                logger.info(
                    "Incoming message",
                    first_name=getattr(user, 'first_name', None),
                    last_name=getattr(user, 'last_name', None),
                    username=getattr(user, 'username', None),
                    chat_id=message.chat.id,
                    message_preview=(message_text or '')[:200],
                    tools_available=len(tools) if tools else 0
                )

                # Process message with LLM and let it decide when to use tools
                response = await self.llm_service.process_message(
                    user_message=message_text,
                    context=context_messages,
                    tools=tools,
                    stream=False
                )
                
                # Track whether any tool (MCP or direct tool call) was used.
                tool_called = False
                websearch_called = False

                # Handle tool calls if present (proper tool_calls structure)
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    tool_called = True
                    tool_results_list, websearch_called = await self._handle_tool_calls(response.tool_calls)
                    
                    # Check if any tools succeeded
                    has_successful_results = any('Error' not in result['result'] for result in tool_results_list)
                    
                    if not has_successful_results:
                        # All tools failed, just respond with an error instead of trying synthesis
                        logger.warning("All tool calls failed, responding with error message")
                        response_text = "Извините, мне не удалось выполнить запрос, так как необходимые инструменты недоступны. Попробуйте переформулировать вопрос без использования поиска."
                    else:
                        logger.info("Tool calls executed, sending results back to model", num_calls=len(tool_results_list))
                        
                        # Save assistant's tool calls as a message
                        tool_calls_metadata = {
                            "tool_calls": [
                                {
                                    "name": tc.function.name,
                                    "arguments": json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                                } for tc in response.tool_calls
                            ]
                        }
                        await session_manager.update_context(
                            session_id=user_session.session_id,
                            role="assistant",
                            content="",  # Empty content as the message is a tool call
                            metadata=tool_calls_metadata
                        )
                        await db.commit()

                        # Save tool results as separate messages
                        for tool_result in tool_results_list:
                            await session_manager.update_context(
                                session_id=user_session.session_id,
                                role="tool",
                                content=tool_result["result"],
                                metadata={"tool_name": tool_result["tool_name"]}
                            )
                            await db.commit()

                        # Update context for the model
                        context_messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                                    }
                                } for tc in response.tool_calls
                            ]
                        })
                        
                        # Add tool results to context
                        for tool_result in tool_results_list:
                            context_messages.append({
                                "role": "tool",
                                "content": tool_result["result"],
                                "tool_name": tool_result["tool_name"]
                            })
                        
                        # Get final response from model
                        final_response = await self.llm_service.process_message(
                            user_message="Please synthesize the tool results into a natural answer.",
                            context=context_messages,
                            tools=None,  # Don't allow more tool calls in the synthesis step
                            stream=False
                        )
                        
                        # Normalize the final response
                        if isinstance(final_response, str):
                            response_text = final_response
                        else:
                            # Check if model returned tool calls again (shouldn't happen but some models do)
                            if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                                logger.warning("Model returned tool calls in synthesis step, ignoring and using error message")
                                # Collect all tool results into a readable format
                                results_summary = "\n".join([f"- {r['tool_name']}: {r['result'][:100]}..." for r in tool_results_list])
                                response_text = f"На основе полученных данных:\n{results_summary}\n\nК сожалению, не удалось синтезировать ответ."
                            else:
                                try:
                                    response_text = getattr(final_response, 'content', str(final_response))
                                except Exception:
                                    response_text = str(final_response)
                else:
                    # Normalize different provider response shapes into a plain string.
                    # Providers may return:
                    # - a plain string
                    # - a JSON string like '{"role":"assistant","content":"..."}'
                    # - an object with a `.content` attribute
                    # - JSON tool parameters (for models that don't support proper tool calling)
                    response_text = None
                    # Plain string case
                    if isinstance(response, str):
                        # Check for natural language tool intent (fallback for models that express intent in plain text)
                        response_lower = response.lower()
                        search_intent_phrases = [
                            'need to search',
                            'i need to search',
                            'searching for',
                            'i should search',
                            'let me search',
                            'поиск',
                            'нужно найти',
                            'нужно поискать',
                            'давайте поищем'
                        ]
                        
                        has_search_intent = any(phrase in response_lower for phrase in search_intent_phrases)
                        
                        # Note: WebSearchMCP fallback removed - model should use proper tool calls
                        
                        # Try to parse JSON strings that contain a message object
                        if not response_text:
                            stripped = response.strip()
                            if (stripped.startswith('{') or stripped.startswith('[')):
                                try:
                                    parsed = json.loads(stripped)
                                    
                                    # If the parsed object looks like a message dict, extract content
                                    if isinstance(parsed, dict) and 'content' in parsed:
                                        response_text = parsed.get('content', '')
                                    # If it's a wrapper like {"message": {"content": ...}}
                                    elif isinstance(parsed, dict) and 'message' in parsed and isinstance(parsed['message'], dict) and 'content' in parsed['message']:
                                        response_text = parsed['message']['content']
                                    else:
                                        # fallback: use original string
                                        response_text = response if not response_text else response_text
                                except Exception:
                                    response_text = response
                            else:
                                response_text = response
                        
                        if not response_text:
                            response_text = response
                    else:
                        # Object-like response: try .content then str()
                        try:
                            response_text = getattr(response, 'content', None)
                        except Exception:
                            response_text = None

                        if response_text is None:
                            # Fallback to string representation
                            response_text = str(response)

                # Normalize and clean response_text before saving/replying
                if response_text is None:
                    response_text = "Извините, но я не смог сгенерировать ответ. Пожалуйста, попробуйте еще раз."
                
                # Prepare message metadata
                metadata = {
                    "tool_called": tool_called,
                    "websearch_called": websearch_called
                }
                
                # Get token count if available
                tokens = None
                if hasattr(response, 'usage') and hasattr(response.usage, 'total_tokens'):
                    tokens = response.usage.total_tokens
                elif hasattr(response, 'tokens'):
                    tokens = response.tokens
                
                # Save the message in the database
                await session_manager.update_context(
                    session_id=user_session.session_id,
                    role="assistant",
                    content=response_text,
                    tokens=tokens,
                    metadata=metadata
                )
                
                await db.commit()
            # Send response (guard network errors so handler doesn't crash)
            try:
                if response_text and response_text.strip():
                    # Try Markdown first, then HTML, then plain text
                    sent = False
                    for parse_mode in ["Markdown", "HTML", None]:
                        try:
                            if parse_mode:
                                await update.message.reply_text(response_text, parse_mode=parse_mode)
                            else:
                                await update.message.reply_text(response_text)
                            sent = True
                            logger.info(f"Successfully sent message with {parse_mode or 'plain text'}")
                            break
                        except Exception as markdown_error:
                            logger.warning(
                                f"Failed to send with {parse_mode or 'plain text'}, trying next option",
                                exc_info=markdown_error
                            )
                            # Don't break here, continue to next parse_mode
                    
                    if not sent:
                        # Last resort: escape problematic characters and send as plain text
                        clean_text = (
                            response_text
                            .replace('*', '\\*')
                            .replace('_', '\\_')
                            .replace('`', '\\`')
                            .replace('[', '\\[')
                            .replace(']', '\\]')
                            .replace('(', '\\(')
                            .replace(')', '\\)')
                        )
                        try:
                            await update.message.reply_text(clean_text)
                            logger.info("Successfully sent escaped plain text")
                        except Exception as final_error:
                            logger.error("Failed to send any format of response", exc_info=final_error)
                else:
                    logger.warning("Response text is empty, sending fallback message")
                    await update.message.reply_text("🤔 Я получил пустой ответ. Попробуйте переформулировать вопрос.")
            except Exception as e:
                logger.warning("Failed to send reply_text", exc_info=e)

            # Log the processed message with full response for debugging
            logger.info(
                "Message processed",
                first_name=getattr(user, 'first_name', None),
                last_name=getattr(user, 'last_name', None),
                username=getattr(user, 'username', None),
                message_preview=(message_text or '')[:200],
                response_full=response_text,  # Full response text for debugging
                message_length=len(message_text or ''),
                response_length=len(response_text or ''),
                tool_called=tool_called,
                websearch_called=websearch_called
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            try:
                await update.message.reply_text(
                    "❌ Я видимо сплю, попробуй спросить позже."
                )
            except Exception as e2:
                logger.warning("Failed to send error reply_text", exc_info=e2)
    
    async def _handle_tool_calls(self, tool_calls) -> tuple[list[dict], bool]:
        """Handle tool calls from LLM
        
        Returns:
            tuple: (list of tool results with tool_name, websearch_called)
                   Each result is {"tool_name": str, "result": str}
        """
        results = []
        websearch_called = False
        
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            parameters = json.loads(tool_call.function.arguments)
            
            # Track if web_search was called
            if tool_name == "web_search":
                websearch_called = True
            
            try:
                result = await self.mcp_manager.execute_tool(tool_name, parameters)
                result_str = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)
                results.append({
                    "tool_name": tool_name,
                    "result": result_str
                })
                logger.info(f"Tool call succeeded: {tool_name}", parameters=parameters)
            except Exception as e:
                results.append({
                    "tool_name": tool_name,
                    "result": f"Error: {str(e)}"
                })
                logger.error(f"Tool call failed: {tool_name}", error=str(e), parameters=parameters)
        
        return results, websearch_called
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
