from abc import ABC, abstractmethod
from typing import Any, Dict


class AgentTool(ABC):
    """Agent工具的抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（用于OpenAI function calling）"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（中文）"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """参数的JSON Schema定义"""
        pass

    def to_openai_tool(self) -> Dict[str, Any]:
        """转换为OpenAI工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具，返回结果字符串"""
        pass
