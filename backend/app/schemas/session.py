import json
from datetime import datetime

from pydantic import BaseModel, field_serializer


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
    tool_calls: list[dict] | None = None   # 工具调用记录（自动从数据库解析）
    created_at: datetime

    @field_serializer('tool_calls', when_used='json')
    def parse_tool_calls(self, value: str | None) -> list[dict] | None:
        """将数据库中的 JSON 字符串解析为列表。"""
        if value is None:
            return None
        if isinstance(value, list):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
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
