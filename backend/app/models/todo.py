from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Todo(Base):
    """任务分解和跟踪模型（已废弃，使用 TodoSnapshot）"""

    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    task = Column(Text, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class TodoSnapshot(Base):
    """TODO 快照模型 - 每个 session 只保留最新状态"""

    __tablename__ = "todo_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)  # 唯一约束
    todos_json = Column(Text, nullable=False)  # JSON 字符串存储完整 todos 列表
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
