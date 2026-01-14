import enum
import json
from typing import Any

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class MessageRole(str, enum.Enum):
    """Message role enum."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"  # 工具响应消息


class Message(Base):
    """Message model for storing chat messages."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    reasoning_content = Column(Text, nullable=True)  # DeepSeek 思考模式内容
    tool_calls = Column(Text, nullable=True)  # 工具调用记录（JSON 字符串）
    tool_call_id = Column(String, nullable=True)  # TOOL 角色消息：关联到 assistant 的 tool_call id
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    session = relationship("Session", back_populates="messages")

    @property
    def tool_calls_parsed(self) -> list[dict[str, Any]] | None:
        """自动解析 tool_calls JSON 字符串为列表。"""
        if not self.tool_calls:
            return None
        try:
            return json.loads(self.tool_calls)
        except (json.JSONDecodeError, TypeError):
            return None

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}', content_length={len(self.content)})>"
