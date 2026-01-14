from typing import AsyncIterator, Dict, List, Optional, Tuple, Any
from openai import AsyncOpenAI
from app.config import get_settings
from app.services.base import AIService
from app.services.deepseek_service import DeepSeekService
import json
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


# 共享的系统提示词模板
_SYSTEM_PROMPT_TEMPLATE = """你是一个专业的网页开发AI助手，通过工具调用在沙箱环境中帮助用户构建Web应用。

## 核心能力

你可以使用以下工具与沙箱环境交互：

1. **todo** - 任务分解和跟踪
   - 参数：{{"action": "add|list|mark_done|clear", "task": "任务描述"}}
   - 用途：在开始工作前，先分解任务并跟踪进度

2. **list** - 列出沙箱中的所有文件
   - 参数：无
   - 用途：查看当前项目结构

3. **read** - 读取文件内容
   - 参数：{{"filename": "index.html"}}
   - 用途：在修改前仔细阅读现有代码

4. **write** - 创建或修改文件
   - 参数：{{"filename": "style.css", "content": "body {{ color: blue; }}"}}
   - 用途：写入文件内容（会完全覆盖，请谨慎）

5. **bash** - 执行bash命令
   - 参数：{{"command": "ls -la"}}
   - 用途：执行文件操作（ls, cat, mkdir, rm, mv, grep等）

6. **check** - 代码质量检查
   - 参数：{{"type": "html|css|js|all", "filename": "index.html"}}
   - 用途：写入代码后运行检查，确保语法正确

## 开发规范

### 文件组织原则
1. **优先使用标准三文件结构**：
   - `index.html` - HTML结构和内容
   - `style.css` - 样式定义
   - `script.js` - 交互逻辑

2. **仅在必要时拆分文件**：
   - 当单个文件超过300行时考虑拆分
   - 功能模块清晰独立时可拆分（如组件化开发）
   - 拆分前先用todo工具说明原因

3. **前端优先原则**：
   - 优先使用HTML/CSS/JavaScript实现功能
   - 避免引入后端依赖（本系统不支持服务端代码）
   - 使用LocalStorage存储简单数据
   - 使用浏览器API实现功能（如fetch、Canvas、WebAudio等）

### 代码质量要求

1. **HTML规范**：
   - 使用语义化标签（header, nav, main, article, section, footer等）
   - 确保可访问性（alt属性、aria-label等）
   - 响应式设计（viewport meta标签）
   - 结构清晰，缩进合理

2. **CSS规范**：
   - 使用现代CSS（Flexbox、Grid、CSS变量）
   - 移动端优先的响应式设计
   - 避免深度嵌套（不超过3层）
   - 使用有意义的类名

3. **JavaScript规范**：
   - 使用现代语法（ES6+：const/let、箭头函数、模板字符串等）
   - 函数式编程优先
   - 适当使用事件委托
   - 避免全局变量污染
   - 使用addEventListener而非onclick属性

4. **安全性**：
   - 输入验证和清理
   - 避免innerHTML直接拼接用户输入
   - 使用textContent而非innerHTML显示用户数据
   - 验证外部API响应

## 工作流程

### 标准开发流程

1. **理解需求** → 用todo工具分解任务
2. **查看现状** → 用list工具了解现有文件
3. **阅读代码** → 用read工具检查相关文件
4. **编写代码** → 用write工具创建/修改文件
5. **验证质量** → 用check工具检查代码（如有必要）
6. **总结说明** → 向用户说明做了什么

### 多轮对话处理

- 每轮对话用户消息会包含最新的沙箱状态和TODO列表
- 注意用户消息中的上下文信息
- 如果用户说"修改刚才的..."，需要先读取相关文件
- 如果用户说"改回来"或"撤销"，需要查看历史消息了解之前的状态
- 如果用户说"继续"，查看待办任务列表

## 注意事项

- **修改前必读**：write工具会完全覆盖文件，修改前务必用read读取
- **沙箱隔离**：所有操作在隔离环境中进行，不会影响用户真实文件系统
- **中文回复**：始终使用中文与用户交流
- **解释清晰**：代码改动后，用简洁的语言说明修改了什么、为什么这样修改
- **最佳实践**：遵循上述开发规范，优先使用标准三文件结构
- **代码检查**：复杂改动后建议使用check工具验证代码质量

## 输出格式

- 不要在回复中输出完整代码（系统会自动显示文件内容）
- 专注于说明你做了什么、为什么这样做
- 如果遇到问题，清晰说明错误原因和解决方案
- 如果用户要求解释代码，可以简要说明关键逻辑，不需要逐行解释
"""


def _extract_json_from_response(content: str) -> Dict[str, str]:
    """从AI响应中提取JSON对象。

    Args:
        content: AI响应内容

    Returns:
        解析后的JSON字典，解析失败返回空字典
    """
    try:
        start_idx = content.find("{")
        end_idx = content.rfind("}") + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    return {}


def _ensure_system_prompt(
    messages: List[Dict[str, str]],
    system_prompt: str
) -> List[Dict[str, str]]:
    """确保消息列表以系统提示开头。

    Args:
        messages: 原始消息列表
        system_prompt: 系统提示内容

    Returns:
        修改后的消息列表
    """
    if not messages:
        return [{"role": "system", "content": system_prompt}]

    if messages[0].get("role") != "system":
        return [{"role": "system", "content": system_prompt}] + messages

    messages[0]["content"] = system_prompt
    return messages


def _build_tool_calls_history(tool_calls) -> List[Dict[str, Any]]:
    """构建工具调用历史记录。

    Args:
        tool_calls: OpenAI格式的工具调用列表

    Returns:
        工具调用历史列表
    """
    history = []
    for tool_call in tool_calls:
        history.append({
            "id": tool_call.id,
            "name": tool_call.function.name,
            "arguments": json.loads(tool_call.function.arguments)
        })
    return history


class OpenAIService(AIService):
    """OpenAI 服务实现（已弃用，保留用于兼容性）。"""

    def __init__(self, is_deepseek: bool = False):
        if is_deepseek:
            self.client = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url
            )
            self.model = settings.deepseek_model
        else:
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
            self.model = settings.openai_model

    async def chat(self, messages: List[Dict]) -> AsyncIterator[str]:
        """流式对话。"""
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
        """修改文件（使用OpenAI）。"""
        system_prompt = """You are a web development assistant. The user will ask you to modify files in their web project.

Current files:
{current_files}

Respond ONLY with a JSON object containing the files to create/modify. Format:
{{
    "index.html": "<html content>",
    "script.js": "<js content>",
    "style.css": "<css content>"
}}

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
        return _extract_json_from_response(content)

    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
        """使用工具调用的对话（OpenAI）。"""
        messages = _ensure_system_prompt(messages, _SYSTEM_PROMPT_TEMPLATE)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.7
            )

            message = response.choices[0].message

            if not message.tool_calls:
                return message.content or "", [], None

            tool_calls_history = _build_tool_calls_history(message.tool_calls)
            content = message.content or ""
            return content, tool_calls_history, None

        except Exception as e:
            logger.error(f"OpenAI tool calling error: {e}")
            return f"AI服务调用失败：{str(e)}", [], None


class ZhipuService(AIService):
    """智谱 AI 服务实现（已弃用，保留用于兼容性）。"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url
        )
        self.model = settings.zhipu_model

    async def chat(self, messages: List[Dict]) -> AsyncIterator[str]:
        """流式对话。"""
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
        """修改文件（使用智谱AI）。"""
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
            temperature=0.7
        )

        content = response.choices[0].message.content
        return _extract_json_from_response(content)

    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
        """使用工具调用的对话（智谱AI）。"""
        messages = _ensure_system_prompt(messages, _SYSTEM_PROMPT_TEMPLATE)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.7
            )

            message = response.choices[0].message

            if not message.tool_calls:
                return message.content or "", [], None

            tool_calls_history = _build_tool_calls_history(message.tool_calls)
            content = message.content or ""
            return content, tool_calls_history, None

        except Exception as e:
            logger.error(f"Zhipu tool calling error: {e}")
            return f"AI服务调用失败：{str(e)}", [], None


class AIServiceFactory:
    """工厂类：创建 AI 服务实例（仅支持 DeepSeek）"""

    @staticmethod
    def create_service(provider: str = "deepseek", enable_reasoning: bool = True) -> AIService:
        """创建 DeepSeek AI 服务实例

        Args:
            provider: AI 提供商（仅支持 "deepseek"）
            enable_reasoning: 是否启用思考模式（默认 True）

        Returns:
            DeepSeekService 实例
        """
        if provider != "deepseek":
            raise ValueError(f"仅支持 DeepSeek AI 提供商，收到: {provider}")

        if not settings.deepseek_api_key:
            raise ValueError("DeepSeek API key 未配置，请在 .env 文件中设置 DEEPSEEK_API_KEY")

        return DeepSeekService(enable_reasoning=enable_reasoning)

    @staticmethod
    def get_default_service() -> AIService:
        """获取默认的 DeepSeek AI 服务（启用思考模式）"""
        return AIServiceFactory.create_service("deepseek", enable_reasoning=True)


def get_ai_service(provider: Optional[str] = None, enable_reasoning: bool = True) -> AIService:
    """获取 DeepSeek AI 服务实例

    Args:
        provider: AI 提供商（忽略，始终使用 DeepSeek）
        enable_reasoning: 是否启用思考模式（默认 True）

    Returns:
        DeepSeekService 实例
    """
    return AIServiceFactory.create_service("deepseek", enable_reasoning=enable_reasoning)
