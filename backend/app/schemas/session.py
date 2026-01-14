from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


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
    created_at: datetime

    class Config:
        from_attributes = True


class SessionDetail(SessionResponse):
    """Session detail with messages."""
    messages: List[MessageResponse] = []


class SessionUpdate(BaseModel):
    """Session update schema."""
    title: Optional[str] = None
    is_public: Optional[bool] = None
