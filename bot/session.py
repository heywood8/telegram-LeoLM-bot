"""Session management"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import redis.asyncio as aioredis
import json

from bot.config import config
from bot.models import User, Session as SessionModel, Message as MessageModel


@dataclass
class Message:
    """Message data class"""
    
    role: str
    content: str
    tokens: Optional[int] = None
    metadata: Optional[Dict] = None


@dataclass
class UserSession:
    """User session data class"""
    
    user_id: int
    session_id: int
    created_at: datetime
    last_active: datetime
    conversation_history: List[Message] = field(default_factory=list)
    active_mcps: List[str] = field(default_factory=list)
    preferences: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


class SessionManager:
    """Manages user sessions and conversation context"""
    
    def __init__(self, db: AsyncSession, redis_url: str = config.redis.url):
        self.db = db
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
    
    async def _get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            self._redis = await aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
    
    async def get_session(self, user_id: int, telegram_id: int, *, telegram_user=None) -> UserSession:
        """Retrieve or create user session"""
        
        # Try to get from cache first
        redis = await self._get_redis()
        cached = await redis.get(f"session:{user_id}")
        
        if cached:
            session_data = json.loads(cached)
            return UserSession(**session_data)
        
        # Get or create user
        user = await self._get_or_create_user(telegram_id, telegram_user)
        
        # Get or create session
        stmt = select(SessionModel).where(SessionModel.user_id == user.id).order_by(SessionModel.last_active.desc())
        result = await self.db.execute(stmt)
        session = result.scalars().first()
        
        if not session:
            session = SessionModel(
                user_id=user.id,
                active_mcps=[],
                session_metadata={},
            )
            self.db.add(session)
            await self.db.flush()
        
        # Load conversation history
        messages = await self._load_messages(session.id)
        
        user_session = UserSession(
            user_id=user.id,
            session_id=session.id,
            created_at=session.created_at,
            last_active=session.last_active,
            conversation_history=messages,
            active_mcps=session.active_mcps or [],
            preferences=user.preferences or {},
            metadata=session.session_metadata or {},
        )
        
        # Cache session
        await redis.setex(
            f"session:{user_id}",
            300,  # 5 minutes TTL
            json.dumps(self._serialize_session(user_session))
        )
        
        return user_session
    
    async def _get_or_create_user(self, telegram_id: int, telegram_user=None) -> User:
        """Get or create user"""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=getattr(telegram_user, 'username', None),
                first_name=getattr(telegram_user, 'first_name', None),
                last_name=getattr(telegram_user, 'last_name', None),
                is_blocked=False,
                is_admin=telegram_id in config.security.admin_ids,
            )
            self.db.add(user)
            await self.db.flush()
        elif telegram_user:
            # Update user info if it has changed
            update_fields = {}
            if user.username != getattr(telegram_user, 'username', None):
                update_fields['username'] = getattr(telegram_user, 'username', None)
            if user.first_name != getattr(telegram_user, 'first_name', None):
                update_fields['first_name'] = getattr(telegram_user, 'first_name', None)
            if user.last_name != getattr(telegram_user, 'last_name', None):
                update_fields['last_name'] = getattr(telegram_user, 'last_name', None)
            
            if update_fields:
                await self.db.execute(
                    update(User)
                    .where(User.id == user.id)
                    .values(**update_fields)
                )
        
        return user
    
    async def _load_messages(self, session_id: int, limit: int = 10) -> List[Message]:
        """Load recent messages (reduced to 10 for more focused context)"""
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        db_messages = result.scalars().all()
        
        # Convert to Message objects (reversed to get chronological order)
        messages = [
            Message(
                role=msg.role,
                content=msg.content,
                tokens=msg.tokens,
                metadata=msg.message_metadata,
            )
            for msg in reversed(db_messages)
        ]
        
        return messages
    
    async def update_context(
        self,
        session_id: int,
        role: str,
        content: str,
        tokens: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Add message to conversation history"""
        
        # Create and save message
        message = MessageModel(
            session_id=session_id,
            role=role,
            content=content,
            tokens=tokens,
            message_metadata=metadata,
        )
        self.db.add(message)
        await self.db.flush()  # Ensure message is saved
        
        # Update session last_active
        stmt = (
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(last_active=datetime.utcnow())
        )
        await self.db.execute(stmt)
        
        # Invalidate cache
        redis = await self._get_redis()
        # We don't know user_id here easily, so we'll rely on TTL
    
    async def get_context_window(
        self,
        session_id: int,
        max_tokens: int = config.resource_limits.max_context_tokens
    ) -> List[Dict[str, str]]:
        """Get recent messages within token limit"""
        
        messages = await self._load_messages(session_id)
        
        # Simple token estimation (can be improved with actual tokenizer)
        context = []
        total_tokens = 0
        
        for msg in reversed(messages):
            msg_tokens = msg.tokens or len(msg.content) // 4  # Rough estimation
            
            if total_tokens + msg_tokens > max_tokens:
                break
            
            context.insert(0, {"role": msg.role, "content": msg.content})
            total_tokens += msg_tokens
        
        return context
    
    async def clear_session(self, session_id: int) -> None:
        """Reset user conversation"""
        
        # Delete all messages
        from sqlalchemy import delete
        stmt = delete(MessageModel).where(MessageModel.session_id == session_id)
        await self.db.execute(stmt)
        
        # Update session
        stmt = (
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(last_active=datetime.utcnow())
        )
        await self.db.execute(stmt)
    
    def _serialize_session(self, session: UserSession) -> Dict:
        """Serialize session for caching"""
        return {
            "user_id": session.user_id,
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "last_active": session.last_active.isoformat(),
            "active_mcps": session.active_mcps,
            "preferences": session.preferences,
            "metadata": session.metadata,
        }
