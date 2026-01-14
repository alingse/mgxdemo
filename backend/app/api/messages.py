import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models.agent_execution import AgentExecutionStep, ExecutionStatus
from app.models.message import Message, MessageRole
from app.models.session import Session as SessionModel
from app.models.todo import Todo
from app.models.user import User
from app.schemas.session import MessageCreate, MessageResponse
from app.services.ai_service import get_ai_service
from app.services.sandbox_service import get_sandbox_service
from app.tools.agent_sandbox import AgentSandbox

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions/{session_id}/messages", tags=["messages"])

# 常量
_MAX_AGENT_ITERATIONS = 10
_CODE_KEYWORDS = [
    "创建", "做一个", "做个", "实现", "修改", "添加", "改成", "改为",
    "写一个", "写个", "生成", "开发", "制作", "设计", "构建"
]
_SYSTEM_PROMPT = """你是一个网页开发助手。你帮助用户创建和修改网页应用。

当用户要求你创建或修改网页应用时，你应该：
1. 理解用户的需求
2. 用简洁的语言说明你要做什么
3. 代码文件会自动被修改，你不需要输出任何特殊标记

例如用户说"帮我做一个 Todo List"，你应该回复：
"好的，我来帮你创建一个 Todo List 应用。它将包含：
- 输入框用于添加新任务
- 任务列表显示
- 完成和删除按钮
- 简洁的样式设计"

不要输出代码，系统会自动处理代码生成。"""


def _convert_tool_calls_to_api_format(tool_calls_data: Any) -> list[dict] | None:
    """将数据库中的 tool_calls 格式转换为 API 格式。

    数据库存储格式:
    [{"id": "call_xxx", "name": "todo", "arguments": {...}}]

    API 需要的格式:
    [{
        "id": "call_xxx",
        "type": "function",
        "function": {
            "name": "todo",
            "arguments": "{...}"  # JSON 字符串
        }
    }]
    """
    if not tool_calls_data:
        return None

    try:
        if isinstance(tool_calls_data, str):
            parsed = json.loads(tool_calls_data)
        else:
            parsed = tool_calls_data

        if not isinstance(parsed, list):
            return None

        api_format = []
        for item in parsed:
            if isinstance(item, dict) and "id" in item:
                if "function" in item:
                    api_format.append(item)
                elif "name" in item and "arguments" in item:
                    api_format.append({
                        "id": item["id"],
                        "type": "function",
                        "function": {
                            "name": item["name"],
                            "arguments": json.dumps(item["arguments"], ensure_ascii=False)
                        }
                    })

        return api_format if api_format else None
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning(f"Failed to convert tool_calls: {e}")
        return None


def _verify_session_access(session_id: str, user_id: int, db: Session) -> SessionModel:
    """验证用户是否有权限访问该会话。"""
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == user_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return session


def _save_execution_step(
    db: Session,
    session_id: str,
    message_id: int,
    user_id: int,
    iteration: int,
    status: ExecutionStatus,
    reasoning_content: str = None,
    tool_name: str = None,
    tool_arguments: dict = None,
    tool_call_id: str = None,
    tool_result: str = None,
    tool_error: str = None,
    progress: float = None
) -> AgentExecutionStep:
    """保存执行步骤到数据库。"""
    step = AgentExecutionStep(
        session_id=session_id,
        message_id=message_id,
        user_id=user_id,
        iteration=iteration,
        status=status,
        reasoning_content=reasoning_content,
        tool_name=tool_name,
        tool_arguments=json.dumps(tool_arguments) if tool_arguments else None,
        tool_call_id=tool_call_id,
        tool_result=tool_result,
        tool_error=tool_error,
        progress=progress
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


async def _build_contextual_user_prompt(
    session_id: str,
    user_id: int,
    user_message: str,
    db: Session
) -> str:
    """构建包含上下文的用户提示词。"""
    context_parts = []

    # 1. 添加沙箱文件状态
    sandbox_service = get_sandbox_service()
    try:
        files = await sandbox_service.list_files(user_id, session_id)
        if files:
            context_parts.append("## 当前沙箱文件")
            context_parts.extend(f"- {filename}" for filename in sorted(files))
            context_parts.append("")
    except Exception as e:
        logger.warning(f"Failed to list files for context: {e}")

    # 2. 添加历史TODO状态
    pending_todos = db.query(Todo).filter(
        Todo.session_id == session_id,
        Todo.completed.is_(False)
    ).order_by(Todo.created_at.asc()).all()

    completed_todos = db.query(Todo).filter(
        Todo.session_id == session_id,
        Todo.completed.is_(True)
    ).order_by(Todo.completed_at.desc()).limit(5).all()

    if pending_todos:
        context_parts.append(f"## 待办任务（{len(pending_todos)}项）")
        context_parts.extend(f"{i}. {todo.task}" for i, todo in enumerate(pending_todos, 1))
        context_parts.append("")

    if completed_todos:
        context_parts.append("## 已完成任务（最近5项）")
        context_parts.extend(f"{i}. {todo.task} ✓" for i, todo in enumerate(completed_todos, 1))
        context_parts.append("")

    # 3. 添加最近的操作摘要
    recent_messages = db.query(Message).filter(
        Message.session_id == session_id,
        Message.role == MessageRole.SYSTEM
    ).order_by(Message.created_at.desc()).limit(3).all()

    if recent_messages:
        context_parts.append("## 最近操作")
        for msg in reversed(recent_messages):
            simplified = msg.content[:150]
            if len(msg.content) > 150:
                simplified += "..."
            context_parts.append(f"- {simplified}")
        context_parts.append("")

    # 4. 用户原始消息
    context_parts.append("## 用户消息")
    context_parts.append(user_message)

    return "\n".join(context_parts)


def _should_modify_files(content: str) -> bool:
    """判断用户消息是否包含文件修改关键词。"""
    return any(keyword in content for keyword in _CODE_KEYWORDS)


async def _prepare_ai_messages(
    session_id: str,
    user_id: int,
    db: Session
) -> list[dict]:
    """准备发送给 AI 的消息列表。"""
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc()).all()

    ai_messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

    for msg in messages:
        msg_dict = {"role": msg.role.value, "content": msg.content}

        if msg.role == MessageRole.USER:
            # 用户消息：添加上下文信息
            msg_dict["content"] = await _build_contextual_user_prompt(
                session_id=session_id,
                user_id=user_id,
                user_message=msg.content,
                db=db
            )
        elif msg.role == MessageRole.ASSISTANT and msg.tool_calls:
            # Assistant 消息有 tool_calls 时，必须添加 reasoning_content
            msg_dict["tool_calls"] = _convert_tool_calls_to_api_format(msg.tool_calls)
            # DeepSeek API 要求：包含 tool_calls 的消息必须同时包含 reasoning_content
            msg_dict["reasoning_content"] = msg.reasoning_content or ""
        elif msg.role == MessageRole.TOOL:
            # TOOL 消息：需要添加 tool_call_id
            msg_dict["tool_call_id"] = msg.tool_call_id or ""
            # TOOL 消息不需要 content 字段（但 API 仍然接受）
        # SYSTEM 消息不需要特殊处理

        ai_messages.append(msg_dict)

    return ai_messages


async def _run_agent_loop(
    ai_messages: list[dict],
    agent_sandbox: AgentSandbox,
    ai_service,
    session_id: str,
    user_id: int,
    db: Session,
    assistant_message: Message
) -> tuple:
    """运行 AI agent 循环。"""
    tools_schema = agent_sandbox.get_tools_schema()
    final_reasoning = None
    final_tool_calls = None
    assistant_response = ""

    for iteration in range(1, _MAX_AGENT_ITERATIONS + 1):
        # 保存思考状态
        _save_execution_step(
            db=db,
            session_id=session_id,
            message_id=assistant_message.id,
            user_id=user_id,
            iteration=iteration,
            status=ExecutionStatus.THINKING,
            progress=min(10 + iteration * 5, 80)
        )

        # 打印调试信息：发送给 API 的消息列表
        logger.info(f"=== Iteration {iteration}: Sending {len(ai_messages)} messages to DeepSeek API ===")
        for idx, msg in enumerate(ai_messages):
            logger.info(
                f"Message {idx}: role={msg.get('role')}, "
                f"has_reasoning={'reasoning_content' in msg}, "
                f"has_tool_calls={'tool_calls' in msg}, "
                f"content_length={len(msg.get('content', ''))}"
            )
            # 如果是 assistant 消息且有 tool_calls，打印详细信息
            if msg.get('role') == 'assistant' and 'tool_calls' in msg:
                logger.warning(
                    f"  Assistant message with tool_calls: "
                    f"reasoning_content={'reasoning_content' in msg}, "
                    f"value='{msg.get('reasoning_content', 'MISSING')[:50]}'"
                )

        assistant_response, tool_calls, reasoning_content = await ai_service.chat_with_tools(
            messages=ai_messages,
            tools=tools_schema
        )

        if reasoning_content:
            final_reasoning = reasoning_content
            logger.info(f"Reasoning (iter {iteration}): {reasoning_content[:500]}...")
            _save_execution_step(
                db=db,
                session_id=session_id,
                message_id=assistant_message.id,
                user_id=user_id,
                iteration=iteration,
                status=ExecutionStatus.THINKING,
                reasoning_content=reasoning_content,
                progress=min(15 + iteration * 5, 85)
            )

        if tool_calls:
            final_tool_calls = tool_calls

        # 构建助手消息历史
        assistant_msg = {
            "role": "assistant",
            "content": assistant_response or ""
        }

        # DeepSeek API 要求：如果有 tool_calls，必须包含 reasoning_content 字段
        if tool_calls:
            assistant_msg["reasoning_content"] = reasoning_content or ""
            assistant_msg["tool_calls"] = tool_calls
            # 打印调试信息
            logger.info(
                f"Assistant msg with tool_calls: "
                f"reasoning_content_length={len(assistant_msg['reasoning_content'])}, "
                f"tool_calls_count={len(tool_calls)}"
            )
        elif reasoning_content:
            assistant_msg["reasoning_content"] = reasoning_content

        ai_messages.append(assistant_msg)

        if not tool_calls:
            break

        # 执行工具调用
        for tool_call in tool_calls:
            func = tool_call.get("function", {})
            tool_name = func.get("name", "")
            tool_arguments_json = func.get("arguments", "{}")

            # 解析 JSON 字符串为字典（DeepSeek API 返回的是 JSON 字符串）
            try:
                if isinstance(tool_arguments_json, str):
                    tool_arguments = json.loads(tool_arguments_json)
                else:
                    tool_arguments = tool_arguments_json
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse tool arguments JSON: {e}")
                tool_arguments = {}

            _save_execution_step(
                db=db,
                session_id=session_id,
                message_id=assistant_message.id,
                user_id=user_id,
                iteration=iteration,
                status=ExecutionStatus.TOOL_CALLING,
                tool_name=tool_name,
                tool_arguments=tool_arguments_json,  # 保存原始 JSON 字符串
                tool_call_id=tool_call.get("id"),
                progress=min(20 + iteration * 8, 90)
            )

            try:
                _save_execution_step(
                    db=db,
                    session_id=session_id,
                    message_id=assistant_message.id,
                    user_id=user_id,
                    iteration=iteration,
                    status=ExecutionStatus.TOOL_EXECUTING,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments_json,  # 保存原始 JSON 字符串
                    tool_call_id=tool_call.get("id"),
                    progress=min(25 + iteration * 8, 92)
                )

                result = await agent_sandbox.execute_tool(
                    tool_name,
                    tool_arguments  # 传递解析后的字典
                )

                _save_execution_step(
                    db=db,
                    session_id=session_id,
                    message_id=assistant_message.id,
                    user_id=user_id,
                    iteration=iteration,
                    status=ExecutionStatus.TOOL_COMPLETED,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments_json,  # 保存原始 JSON 字符串
                    tool_call_id=tool_call.get("id"),
                    tool_result=result[:1000] if result else None,
                    progress=min(30 + iteration * 8, 95)
                )

                # 保存 TOOL 消息到数据库
                tool_message = Message(
                    session_id=session_id,
                    role=MessageRole.TOOL,
                    content=str(result),
                    tool_call_id=tool_call.get("id", "")
                )
                db.add(tool_message)

                ai_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": str(result)
                })
                logger.info(f"Tool {tool_name} executed")

            except Exception as e:
                error_msg = f"工具 {tool_name} 执行失败: {str(e)}"
                logger.error(error_msg)

                _save_execution_step(
                    db=db,
                    session_id=session_id,
                    message_id=assistant_message.id,
                    user_id=user_id,
                    iteration=iteration,
                    status=ExecutionStatus.FAILED,
                    tool_name=tool_name,
                    tool_arguments=tool_arguments_json,  # 保存原始 JSON 字符串
                    tool_call_id=tool_call.get("id"),
                    tool_error=error_msg,
                    progress=min(30 + iteration * 8, 95)
                )

                # 保存 TOOL 错误消息到数据库
                tool_message = Message(
                    session_id=session_id,
                    role=MessageRole.TOOL,
                    content=error_msg,
                    tool_call_id=tool_call.get("id", "")
                )
                db.add(tool_message)

                ai_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": error_msg
                })

    # 保存最终完成状态
    _save_execution_step(
        db=db,
        session_id=session_id,
        message_id=assistant_message.id,
        user_id=user_id,
        iteration=iteration,
        status=ExecutionStatus.COMPLETED,
        progress=100.0
    )

    return assistant_response, final_reasoning, final_tool_calls


async def _handle_legacy_mode(
    ai_service,
    ai_messages: list[dict],
    message_create: MessageCreate,
    current_user: User,
    session_id: str,
    db: Session
) -> Message:
    """处理传统对话模式（不使用工具）。"""
    assistant_response = ""
    async for chunk in ai_service.chat(ai_messages):
        assistant_response += chunk

    assistant_message = Message(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content=assistant_response
    )
    db.add(assistant_message)

    if _should_modify_files(message_create.content):
        await _modify_files_in_sandbox(
            ai_service,
            message_create.content,
            current_user.id,
            session_id,
            db
        )

    return assistant_message


async def _modify_files_in_sandbox(
    ai_service,
    instruction: str,
    user_id: int,
    session_id: str,
    db: Session
) -> None:
    """在沙箱中修改文件。"""
    sandbox_service = get_sandbox_service()
    current_files = await sandbox_service.get_all_files(user_id, session_id)

    try:
        updated_files = await ai_service.modify_files(instruction, current_files)

        if updated_files:
            await sandbox_service.update_files(user_id, session_id, updated_files)

            file_names = ", ".join(updated_files.keys())
            system_msg = Message(
                session_id=session_id,
                role=MessageRole.SYSTEM,
                content=f"✅ 已更新文件: {file_names}"
            )
            db.add(system_msg)
    except Exception as e:
        error_msg = Message(
            session_id=session_id,
            role=MessageRole.SYSTEM,
            content=f"❌ 更新文件时出错: {str(e)}"
        )
        db.add(error_msg)


@router.get("", response_model=list[MessageResponse])
async def list_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> list[Message]:
    """获取会话中的所有消息。"""
    _verify_session_access(session_id, current_user.id, db)

    return db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc()).all()


@router.post("", response_model=MessageResponse)
async def create_message(
    session_id: str,
    message_create: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Message:
    """创建新消息并获取 AI 响应。"""
    settings = get_settings()
    session = _verify_session_access(session_id, current_user.id, db)

    # 保存用户消息
    user_message = Message(
        session_id=session_id,
        role=MessageRole.USER,
        content=message_create.content
    )
    db.add(user_message)

    # 准备 AI 消息
    ai_messages = await _prepare_ai_messages(session_id, current_user.id, db)
    ai_service = get_ai_service()

    if settings.enable_agent_loop:
        try:
            agent_sandbox = AgentSandbox(session_id, current_user.id, db)

            # 先创建空的助手消息用于关联执行步骤
            assistant_message = Message(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content="",
                reasoning_content=None,
                tool_calls=None
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)

            logger.info(
                f"Starting agent loop for session {session_id}, "
                f"message_id={assistant_message.id}"
            )

            assistant_response, final_reasoning, final_tool_calls = await _run_agent_loop(
                ai_messages,
                agent_sandbox,
                ai_service,
                session_id,
                current_user.id,
                db,
                assistant_message,
            )

            assistant_message.content = assistant_response or ""
            assistant_message.reasoning_content = final_reasoning
            if final_tool_calls:
                assistant_message.tool_calls = json.dumps(final_tool_calls)
            else:
                assistant_message.tool_calls = None
            db.commit()
            db.refresh(assistant_message)

        except Exception as e:
            logger.error(f"Agent loop error: {e}", exc_info=True)
            assistant_message = Message(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=f"AI服务出错：{str(e)}"
            )
            db.add(assistant_message)
    else:
        assistant_message = await _handle_legacy_mode(
            ai_service, ai_messages, message_create, current_user, session_id, db
        )

    # 更新会话时间戳
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(assistant_message)

    return assistant_message


@router.get("/_internal/latest/execution-steps", response_model=list[dict])
async def get_latest_execution_steps(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> list[dict]:
    """获取会话中最新一条消息的执行步骤（用于轮询最新进度）。

    使用 /_internal/ 前缀避免与 /{message_id}/execution-steps 路由冲突。
    """
    _verify_session_access(session_id, current_user.id, db)

    latest_message = db.query(Message).filter(
        Message.session_id == session_id,
        Message.role == MessageRole.ASSISTANT
    ).order_by(Message.created_at.desc()).first()

    if not latest_message:
        return []

    steps = db.query(AgentExecutionStep).filter(
        AgentExecutionStep.session_id == session_id,
        AgentExecutionStep.message_id == latest_message.id
    ).order_by(AgentExecutionStep.created_at.asc()).all()

    return [step.to_dict() for step in steps]


@router.get("/{message_id}/execution-steps", response_model=list[dict])
async def get_execution_steps(
    session_id: str,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> list[dict]:
    """获取指定消息的所有执行步骤（实时进度）。"""
    _verify_session_access(session_id, current_user.id, db)

    steps = db.query(AgentExecutionStep).filter(
        AgentExecutionStep.session_id == session_id,
        AgentExecutionStep.message_id == message_id
    ).order_by(AgentExecutionStep.created_at.asc()).all()

    return [step.to_dict() for step in steps]
