from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, List, Optional
from openai import AsyncOpenAI
from app.config import get_settings
from app.models.message import Message, MessageRole
import httpx
import json

settings = get_settings()


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


class OpenAIService(AIService):
    """OpenAI service implementation."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        self.model = settings.openai_model

    async def chat(self, messages: List[Dict]) -> AsyncIterator[str]:
        """Stream chat completion using OpenAI."""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def modify_files(
        self,
        instruction: str,
        current_files: Dict[str, str]
    ) -> Dict[str, str]:
        """Modify files using OpenAI."""
        system_prompt = """You are a web development assistant. The user will ask you to modify files in their web project.

Current files:
{current_files}

Respond ONLY with a JSON object containing the files to create/modify. Format:
{
    "index.html": "<html content>",
    "script.js": "<js content>",
    "style.css": "<css content>"
}

Only include files that need to be created or modified. Do not include any explanation outside the JSON."""

        current_files_str = json.dumps(current_files, indent=2)
        messages = [
            {"role": "system", "content": system_prompt.format(current_files=current_files_str)},
            {"role": "user", "content": instruction}
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7
        )

        content = response.choices[0].message.content

        # Extract JSON from response
        try:
            # Find JSON in the response
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        return {}


class ZhipuService(AIService):
    """Zhipu AI (GLM) service implementation."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url
        )
        self.model = settings.zhipu_model

    async def chat(self, messages: List[Dict]) -> AsyncIterator[str]:
        """Stream chat completion using Zhipu AI."""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def modify_files(
        self,
        instruction: str,
        current_files: Dict[str, str]
    ) -> Dict[str, str]:
        """Modify files using Zhipu AI."""
        system_prompt = """你是一个网页开发助手。用户会要求你修改他们的网页项目中的文件。

当前文件：
{current_files}

请只回复一个 JSON 对象，包含需要创建/修改的文件。格式：
{
    "index.html": "<html 内容>",
    "script.js": "<js 内容>",
    "style.css": "<css 内容>"
}

只包含需要创建或修改的文件。不要在 JSON 外添加任何解释。"""

        current_files_str = json.dumps(current_files, indent=2)
        messages = [
            {"role": "system", "content": system_prompt.format(current_files=current_files_str)},
            {"role": "user", "content": instruction}
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7
        )

        content = response.choices[0].message.content

        # Extract JSON from response
        try:
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        return {}


class AIServiceFactory:
    """Factory for creating AI service instances."""

    @staticmethod
    def create_service(provider: str) -> AIService:
        """Create an AI service instance based on provider."""
        if provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return OpenAIService()
        elif provider == "zhipu":
            if not settings.zhipu_api_key:
                raise ValueError("Zhipu API key not configured")
            return ZhipuService()
        elif provider == "anthropic":
            raise NotImplementedError("Anthropic service not yet implemented")
        else:
            raise ValueError(f"Unknown AI provider: {provider}")

    @staticmethod
    def get_default_service() -> AIService:
        """Get the default AI service."""
        return AIServiceFactory.create_service(settings.default_ai_provider)


def get_ai_service(provider: Optional[str] = None) -> AIService:
    """Get an AI service instance."""
    if provider is None:
        return AIServiceFactory.get_default_service()
    return AIServiceFactory.create_service(provider)
