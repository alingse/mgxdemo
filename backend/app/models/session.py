import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Session(Base):
    """Session model for storing user conversations."""

    __tablename__ = "sessions"

    id = Column(String, primary_key=True, index=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


# Add back_populates to User model
from app.models.user import User

User.sessions = relationship("Session", back_populates="user")
