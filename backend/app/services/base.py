from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class AIService(ABC):
    """Abstract base class for AI services."""

    @abstractmethod
    async def chat(self, messages: list[dict]) -> AsyncIterator[str]:
        """Stream chat completion."""
        pass

    @abstractmethod
    async def modify_files(
        self,
        instruction: str,
        current_files: dict[str, str]
    ) -> dict[str, str]:
        """Modify sandbox files based on instruction."""
        pass

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]], str | None]:
        """Chat with tool calling support.

        Args:
            messages: Conversation history
            tools: Available tools in OpenAI format

        Returns:
            (final_response, tool_calls_history, reasoning_content)
            reasoning_content 为 DeepSeek 思考模式的推理内容，其他服务返回 None
        """
        pass
