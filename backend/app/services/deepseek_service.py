from typing import AsyncIterator, Dict, List, Optional, Tuple, Any
from openai import AsyncOpenAI
from app.config import get_settings
from app.services.base import AIService
import logging

import json

logger = logging.getLogger(__name__)
settings = get_settings()


# DeepSeek 专用系统提示词（与共享模板类似但更简洁）
_DEEPSEEK_SYSTEM_PROMPT = """你是一个专业的网页开发AI助手，通过工具调用在沙箱环境中帮助用户构建Web应用。

## 可用工具

1. **todo** - 任务分解和跟踪（action: add|list|mark_done|clear）
2. **list** - 列出沙箱中的所有文件
3. **read** - 读取文件内容
4. **write** - 创建或修改文件（会完全覆盖）
5. **bash** - 执行bash命令（ls, cat, mkdir, rm, mv, grep等）
6. **check** - 代码质量检查（type: html|css|js|all）

## 开发规范

1. **文件组织**：优先使用标准三文件结构（index.html, style.css, script.js）
2. **前端优先**：使用HTML/CSS/JavaScript，避免后端依赖
3. **代码质量**：使用现代ES6+语法、语义化HTML、响应式CSS
4. **安全性**：验证输入、避免innerHTML拼接用户数据

## 工作流程

1. 用 **todo** 分解任务
2. 用 **list** 查看现有文件
3. 用 **read** 读取要修改的文件
4. 用 **write** 创建/修改文件
5. 用 **check** 验证代码质量
6. 向用户说明做了什么

## 注意事项

- **修改前必读**：write会完全覆盖文件，务必先用read读取
- **中文回复**：始终使用中文与用户交流
- **简洁说明**：不要输出完整代码，专注于说明修改了什么"""


def _ensure_system_prompt(
    messages: List[Dict[str, str]],
    system_prompt: str
) -> List[Dict[str, str]]:
    """确保消息列表以系统提示开头。"""
    if not messages:
        return [{"role": "system", "content": system_prompt}]

    if messages[0].get("role") != "system":
        return [{"role": "system", "content": system_prompt}] + messages

    messages[0]["content"] = system_prompt
    return messages


def _build_tool_calls_history(tool_calls) -> List[Dict[str, Any]]:
    """构建工具调用历史记录。"""
    history = []
    for tool_call in tool_calls:
        history.append({
            "id": tool_call.id,
            "name": tool_call.function.name,
            "arguments": json.loads(tool_call.function.arguments)
        })
    return history


def _extract_json_from_response(content: str) -> Dict[str, str]:
    """从AI响应中提取JSON对象。"""
    try:
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            return json.loads(content[start_idx:end_idx])
    except json.JSONDecodeError:
        pass
    return {}


class DeepSeekService(AIService):
    """DeepSeek AI 服务实现（支持思考模式）"""

    def __init__(self, enable_reasoning: bool = True):
        """
        初始化 DeepSeek 服务

        Args:
            enable_reasoning: 是否启用思考模式（默认 True）
        """
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url
        )
        self.enable_reasoning = enable_reasoning

        # 根据是否启用思考模式选择模型
        if enable_reasoning:
            self.model = "deepseek-reasoner"  # 思考模式模型
        else:
            self.model = settings.deepseek_model or "deepseek-chat"

        logger.info(f"DeepSeek service initialized with model: {self.model}, reasoning: {enable_reasoning}")

    async def chat(self, messages: List[Dict]) -> AsyncIterator[str]:
        """流式对话（不使用工具）"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **({"extra_body": {"thinking": {"type": "enabled"}}} if self.enable_reasoning else {})
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def modify_files(
        self,
        instruction: str,
        current_files: Dict[str, str]
    ) -> Dict[str, str]:
        """修改文件（使用思考模式）"""
        system_prompt = """你是一个网页开发助手。用户会要求你修改他们的网页项目中的文件。

当前文件：
{current_files}

请只回复一个 JSON 对象，包含需要创建/修改的文件。格式：
{{
    "index.html": "<html 内容>",
    "script.js": "<js 内容>",
    "style.css": "<css 内容>"
}}

只包含需要创建或修改的文件。不要在 JSON 外添加任何解释。"""

        current_files_str = json.dumps(current_files, indent=2)
        messages = [
            {"role": "system", "content": system_prompt.format(current_files=current_files_str)},
            {"role": "user", "content": instruction}
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            **({"extra_body": {"thinking": {"type": "enabled"}}} if self.enable_reasoning else {})
        )

        content = response.choices[0].message.content

        # 如果有思考内容，记录日志
        if hasattr(response.choices[0].message, 'reasoning_content'):
            reasoning = response.choices[0].message.reasoning_content
            logger.info(f"DeepSeek reasoning for modify_files: {reasoning[:500]}...")

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

    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
        """使用工具调用的对话（支持思考模式）。

        Args:
            messages: 对话历史
            tools: 可用工具列表

        Returns:
            (最终回复, 工具调用列表, 推理内容)
        """
        messages = _ensure_system_prompt(messages, _DEEPSEEK_SYSTEM_PROMPT)

        logger.info(
            f"DeepSeek chat_with_tools: {len(messages)} messages, "
            f"{len(tools)} tools, reasoning={self.enable_reasoning}"
        )

        try:
            request_params = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto"
            }

            if self.enable_reasoning:
                request_params["extra_body"] = {"thinking": {"type": "enabled"}}

            response = await self.client.chat.completions.create(**request_params)
            message = response.choices[0].message

            reasoning_content = None
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                reasoning_content = message.reasoning_content
                logger.info(f"DeepSeek reasoning: {len(reasoning_content)} chars")

            if not message.tool_calls:
                logger.info("No tool calls, returning final answer")
                return message.content or "", [], reasoning_content

            tool_calls_history = _build_tool_calls_history(message.tool_calls)
            logger.info(f"Received {len(tool_calls_history)} tool calls")

            return message.content or "", tool_calls_history, reasoning_content

        except Exception as e:
            logger.error(f"DeepSeek tool calling error: {e}")
            return f"AI服务调用失败：{str(e)}", [], None

    def clear_reasoning_from_messages(self, messages: List[Dict]) -> None:
        """清除消息历史中的 reasoning_content

        在新的用户问题开始时调用，以节省带宽。
        """
        for message in messages:
            if isinstance(message, dict) and "reasoning_content" in message:
                del message["reasoning_content"]
            elif hasattr(message, 'reasoning_content'):
                message.reasoning_content = None

        logger.info("Cleared reasoning_content from message history")
