import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.base import AIService

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

## 实现偏好（非常重要）

- 默认使用原生 HTML、CSS、JavaScript 实现功能。
- 不要使用任何前端框架或库：React、Vue、Svelte、Angular、jQuery 等。
- 不要使用 JSX、TSX 或 TypeScript；仅使用原生 ES6+。
- 不要引入打包/构建工具或包管理：Vite、Webpack、Rollup、Babel、npm/pnpm/yarn 等。
- 不要通过 CDN 引入大型 UI/JS 框架（如 Bootstrap、Tailwind、Ant Design 等），除非用户明确要求。
- 组件化与状态管理请用原生 DOM API、函数封装与事件委托来完成。
- 优先使用三文件结构：index.html、style.css、script.js；脚本用普通 <script> 标签（非模块）即可。
- 资源路径使用相对路径，避免额外目录或复杂结构，除非必须。

## 代码质量与安全

- 使用语义化 HTML、响应式 CSS（flex/grid），现代 ES6+ 语法。
- 表单与输入做最小必要的校验；处理用户输入时避免使用 innerHTML 拼接，使用 textContent/innerText 或安全的 DOM API。
- 避免全局变量污染，封装局部作用域；必要时使用 IIFE 或模块化结构但不引入打包链路。
- 可访问性：合理使用 label、aria-* 属性与可聚焦元素。

## 工作流程

1. 用 **todo** 分解任务
2. 用 **list** 查看现有文件
3. 用 **read** 读取要修改的文件
4. 用 **write** 创建/修改文件（修改前务必先 read）
5. 用 **check** 验证代码质量
6. 向用户简洁说明改动点与使用方式

## 交互约定

- 如果用户明确要求使用 React/其他框架，先进行确认；若无特别要求，一律用原生方案实现同等效果。
- 如需外部依赖（图标、小型 polyfill），先征求用户同意，再最小化引入。

## 注意事项

- 始终用中文与用户交流。
- 回答中不要粘贴完整代码，重点说明做了什么与如何使用；完整代码请写入文件。
"""


def _ensure_system_prompt(
    messages: list[dict[str, str]],
    system_prompt: str
) -> list[dict[str, str]]:
    """确保消息列表以系统提示开头。"""
    if not messages:
        return [{"role": "system", "content": system_prompt}]

    if messages[0].get("role") != "system":
        return [{"role": "system", "content": system_prompt}] + messages

    messages[0]["content"] = system_prompt
    return messages


def _build_tool_calls_history(tool_calls) -> list[dict[str, Any]]:
    """构建工具调用历史记录（符合 OpenAI API 格式）。

    OpenAI/DeepSeek API 要求的格式：
    {
        "id": "call_xxx",
        "type": "function",
        "function": {
            "name": "tool_name",
            "arguments": "{...}"  # JSON 字符串
        }
    }
    """
    history = []
    for tool_call in tool_calls:
        history.append({
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments  # 保持原始 JSON 字符串
            }
        })
    return history


def _extract_json_from_response(content: str) -> dict[str, str]:
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

        logger.info(
            f"DeepSeek service initialized with model: {self.model}, "
            f"reasoning: {enable_reasoning}"
        )

    async def chat(self, messages: list[dict]) -> AsyncIterator[str]:
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
        current_files: dict[str, str]
    ) -> dict[str, str]:
        """修改文件（使用思考模式）"""
        system_prompt = """你是一个网页开发助手。用户会要求你修改他们的网页项目中的文件。

当前文件：
{current_files}

## 实现偏好（必须遵守）

- 默认使用原生 HTML、CSS、JavaScript 实现功能。
- 不要使用任何前端框架或库：React、Vue、Svelte、Angular、jQuery 等。
- 不要使用 JSX、TSX 或 TypeScript；仅使用原生 ES6+。
- 不要引入打包/构建工具或包管理：Vite、Webpack、Rollup、Babel、npm/pnpm/yarn 等。
- 不要通过 CDN 引入大型 UI/JS 框架（如 Bootstrap、Tailwind、Ant Design 等），除非用户明确要求。
- 组件化与状态管理请用原生 DOM API、函数封装与事件委托来完成。
- 优先使用三文件结构：index.html、style.css、script.js；脚本用普通 <script> 标签（非模块）即可。
- 如果用户明确要求使用框架，先用原生方案实现，并在回复中说明可以替换为框架。

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
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]], str | None]:
        """使用工具调用的对话（支持思考模式）。

        Args:
            messages: 对话历史
            tools: 可用工具列表

        Returns:
            (最终回复, 工具调用列表, 推理内容)
        """
        logger.info(f"=== chat_with_tools START ===")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  Enable reasoning: {self.enable_reasoning}")

        messages = _ensure_system_prompt(messages, _DEEPSEEK_SYSTEM_PROMPT)

        logger.info(
            f"DeepSeek chat_with_tools: {len(messages)} messages, "
            f"{len(tools)} tools, reasoning={self.enable_reasoning}"
        )

        try:
            # 打印调试信息：检查消息格式
            logger.info("=== 检查发送给 DeepSeek API 的消息格式 ===")
            for idx, msg in enumerate(messages):
                has_rc = "reasoning_content" in msg
                has_tc = "tool_calls" in msg
                role = msg.get("role", "unknown")

                # 如果是 assistant 消息且有 tool_calls，检查是否有 reasoning_content
                if role == "assistant" and has_tc:
                    if not has_rc:
                        logger.error(
                            f"❌ 消息 {idx}: role=assistant, 有 tool_calls 但缺少 reasoning_content!"
                        )
                    else:
                        rc_value = msg.get("reasoning_content", "")
                        logger.info(
                            f"✓ 消息 {idx}: role=assistant, 有 tool_calls, reasoning_content长度={len(rc_value)}"
                        )
                else:
                    logger.info(
                        f"  消息 {idx}: role={role}, has_reasoning={has_rc}, has_tool_calls={has_tc}"
                    )

            request_params = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto"
            }

            if self.enable_reasoning:
                request_params["extra_body"] = {"thinking": {"type": "enabled"}}

            logger.info(f"=== Calling DeepSeek API ===")
            logger.info(f"  URL: {settings.deepseek_base_url}")
            logger.info(f"  Request params keys: {list(request_params.keys())}")

            response = await self.client.chat.completions.create(**request_params)

            logger.info(f"=== DeepSeek API returned ===")
            message = response.choices[0].message
            logger.info(f"  Has content: {bool(message.content)}")
            logger.info(f"  Has tool_calls: {bool(message.tool_calls)}")
            logger.info(f"  Has reasoning_content: {hasattr(message, 'reasoning_content')}")

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
            logger.error(f"=== DeepSeek API ERROR ===")
            logger.error(f"  Error type: {type(e).__name__}")
            logger.error(f"  Error message: {e}", exc_info=True)
            return f"AI服务调用失败：{str(e)}", [], None

    def clear_reasoning_from_messages(self, messages: list[dict]) -> None:
        """清除消息历史中的 reasoning_content

        在新的用户问题开始时调用，以节省带宽。
        """
        for message in messages:
            if isinstance(message, dict) and "reasoning_content" in message:
                del message["reasoning_content"]
            elif hasattr(message, 'reasoning_content'):
                message.reasoning_content = None

        logger.info("Cleared reasoning_content from message history")
