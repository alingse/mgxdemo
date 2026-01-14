from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.session import MessageCreate, MessageResponse
from app.models.user import User
from app.models.session import Session as SessionModel
from app.models.message import Message, MessageRole
from app.core.deps import get_current_user
from app.services.ai_service import get_ai_service
from app.services.sandbox_service import get_sandbox_service
from datetime import datetime

router = APIRouter(prefix="/api/sessions/{session_id}/messages", tags=["messages"])


def _verify_session_access(session_id: str, user_id: int, db: Session) -> SessionModel:
    """Verify user has access to the session."""
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


@router.get("", response_model=List[MessageResponse])
async def list_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all messages in a session."""
    session = _verify_session_access(session_id, current_user.id, db)

    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc()).all()

    return messages


@router.post("", response_model=MessageResponse)
async def create_message(
    session_id: str,
    message_create: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new message and get AI response."""
    session = _verify_session_access(session_id, current_user.id, db)

    # Save user message
    user_message = Message(
        session_id=session_id,
        role=MessageRole.USER,
        content=message_create.content
    )
    db.add(user_message)

    # Get conversation history
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc()).all()

    # Prepare messages for AI
    ai_messages = []
    system_prompt = """你是一个网页开发助手。你帮助用户创建和修改网页应用。

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

    ai_messages.append({"role": "system", "content": system_prompt})
    for msg in messages:
        ai_messages.append({
            "role": msg.role.value,
            "content": msg.content
        })

    # Get AI response
    ai_service = get_ai_service()
    assistant_response = ""

    async for chunk in ai_service.chat(ai_messages):
        assistant_response += chunk

    # Save assistant message
    assistant_message = Message(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content=assistant_response
    )
    db.add(assistant_message)

    # Update session timestamp
    session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(assistant_message)

    # 智能判断是否需要修改文件
    # 检测关键词：创建、做、实现、修改、添加、改、写、生成等
    code_keywords = ["创建", "做一个", "做个", "实现", "修改", "添加", "改成", "改为",
                     "写一个", "写个", "生成", "开发", "制作", "设计", "构建"]

    user_content_lower = message_create.content.lower()
    should_modify_files = any(keyword in message_create.content for keyword in code_keywords)

    # 如果用户消息包含代码相关关键词，自动调用 AI 修改文件
    if should_modify_files:
        sandbox_service = get_sandbox_service()
        current_files = await sandbox_service.get_all_files(current_user.id, session_id)

        # 构建完整的指令，包含用户原始请求
        instruction = f"{message_create.content}"

        # 获取 AI 修改后的文件
        try:
            updated_files = await ai_service.modify_files(instruction, current_files)

            if updated_files:
                await sandbox_service.update_files(current_user.id, session_id, updated_files)

                # 添加系统消息通知文件已更新
                file_names = ", ".join(updated_files.keys())
                system_msg = Message(
                    session_id=session_id,
                    role=MessageRole.SYSTEM,
                    content=f"✅ 已更新文件: {file_names}"
                )
                db.add(system_msg)
                db.commit()
        except Exception as e:
            # 添加错误消息
            error_msg = Message(
                session_id=session_id,
                role=MessageRole.SYSTEM,
                content=f"❌ 更新文件时出错: {str(e)}"
            )
            db.add(error_msg)
            db.commit()

    return assistant_message
