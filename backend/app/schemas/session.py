import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class SessionBase(BaseModel):
    """Base session schema."""
    title: str


class SessionCreate(SessionBase):
    """Session creation schema."""
    pass


class SessionResponse(SessionBase):
    """Session response schema."""
    id: str
    is_public: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    """Base message schema."""
    content: str


class MessageCreate(MessageBase):
    """Message creation schema."""
    pass


class MessageResponse(MessageBase):
    """Message response schema."""
    id: int
    role: str
    reasoning_content: str | None = None  # AI 思考内容
    tool_calls: list[dict] | None = None   # 工具调用记录（自动从数据库 JSON 字符串解析）
    tool_call_id: str | None = None  # TOOL 角色消息的 tool_call_id
    created_at: datetime

    @field_validator('tool_calls', mode='before')
    @classmethod
    def parse_tool_calls(cls, value: Any) -> list[dict] | None:
        """将数据库中的 JSON 字符串解析为列表（在验证前执行）。"""
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    class Config:
        from_attributes = True


class SessionDetail(SessionResponse):
    """Session detail with messages."""
    messages: list[MessageResponse] = []


class SessionUpdate(BaseModel):
    """Session update schema."""
    title: str | None = None
    is_public: bool | None = None
