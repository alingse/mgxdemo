"""Agent execution tracking models."""
import enum
import json

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ExecutionStatus(str, enum.Enum):
    """Agent execution status enum."""
    THINKING = "thinking"           # AI 正在思考
    TOOL_CALLING = "tool_calling"   # AI 调用工具
    TOOL_EXECUTING = "tool_executing" # 工具正在执行
    TOOL_COMPLETED = "tool_completed" # 工具执行完成
    FINALIZING = "finalizing"       # 生成最终答案
    COMPLETED = "completed"         # 完成
    FAILED = "failed"               # 失败


class AgentExecutionStep(Base):
    """单次 AI 回复的执行步骤记录"""

    __tablename__ = "agent_execution_steps"

    id = Column(Integer, primary_key=True, index=True)

    # 关联信息
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # 执行信息
    iteration = Column(Integer, nullable=False, default=1)  # 第几轮循环
    status = Column(Enum(ExecutionStatus), nullable=False, default=ExecutionStatus.THINKING)

    # 思考内容（reasoning_content）
    reasoning_content = Column(Text, nullable=True)

    # 工具调用信息
    tool_name = Column(String(100), nullable=True)
    tool_arguments = Column(Text, nullable=True)  # JSON 字符串
    tool_call_id = Column(String(100), nullable=True)

    # 工具执行结果
    tool_result = Column(Text, nullable=True)
    tool_error = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # 进度（0-100）
    progress = Column(Float, nullable=True, default=0)

    # Relationships
    message = relationship("Message", backref="execution_steps")
    session = relationship("Session", backref="execution_steps")

    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "iteration": self.iteration,
            "status": self.status.value,
            "reasoning_content": self.reasoning_content,
            "tool_name": self.tool_name,
            "tool_arguments": json.loads(self.tool_arguments) if self.tool_arguments else None,
            "tool_result": self.tool_result,
            "tool_error": self.tool_error,
            "progress": self.progress,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<AgentExecutionStep(id={self.id}, status={self.status}, tool={self.tool_name})>"
