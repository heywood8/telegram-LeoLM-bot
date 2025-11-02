"""LLM integration layer"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Union, AsyncGenerator
import structlog

logger = structlog.get_logger()


class LLMError(Exception):
    """LLM-related errors"""
    pass


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
