from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, List, Optional, Tuple, Any


class AIService(ABC):
    """Abstract base class for AI services."""

    @abstractmethod
    async def chat(self, messages: List[Dict]) -> AsyncIterator[str]:
        """Stream chat completion."""
        pass

    @abstractmethod
    async def modify_files(
        self,
        instruction: str,
        current_files: Dict[str, str]
    ) -> Dict[str, str]:
        """Modify sandbox files based on instruction."""
        pass

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
        """Chat with tool calling support.

        Args:
            messages: Conversation history
            tools: Available tools in OpenAI format

        Returns:
            (final_response, tool_calls_history, reasoning_content)
            reasoning_content 为 DeepSeek 思考模式的推理内容，其他服务返回 None
        """
        pass
