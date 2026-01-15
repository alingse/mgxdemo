from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.todo import Todo
from app.tools.base import AgentTool


class TodoTool(AgentTool):
    """任务分解和跟踪工具"""

    def __init__(self, session_id: str, db: Session):
        self.session_id = session_id
        self.db = db

    @property
    def name(self) -> str:
        return "todo"

    @property
    def description(self) -> str:
        return (
            "任务分解和跟踪工具。用于记录用户需求并将其分解为小任务。\n"
            "操作类型：\n"
            "- add: 添加新任务\n"
            "- list: 列出所有任务\n"
            "- mark_done: 标记任务完成\n"
            "- clear: 清除所有任务"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "mark_done", "clear"],
                    "description": "操作类型",
                },
                "task": {
                    "type": "string",
                    "description": "任务描述（action为add或mark_done时需要）",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, task: str = None) -> str:
        """执行TODO操作"""
        try:
            if action == "add":
                if not task:
                    return "错误：添加任务时必须提供task参数"
                return await self._add_task(task)
            elif action == "list":
                return await self._list_tasks()
            elif action == "mark_done":
                if not task:
                    return "错误：标记任务完成时必须提供task参数"
                return await self._mark_done(task)
            elif action == "clear":
                return await self._clear_tasks()
            else:
                return f"错误：未知的操作类型 '{action}'"
        except Exception as e:
            return f"执行TODO操作时出错：{str(e)}"

    async def _add_task(self, task: str) -> str:
        """添加新任务"""
        todo = Todo(session_id=self.session_id, task=task, completed=False)
        self.db.add(todo)
        self.db.commit()
        return f"已添加任务：{task}"

    async def _list_tasks(self) -> str:
        """列出所有任务"""
        todos = (
            self.db.query(Todo)
            .filter(Todo.session_id == self.session_id)
            .order_by(Todo.created_at)
            .all()
        )

        if not todos:
            return "当前没有任务。"

        lines = ["任务列表："]
        for i, todo in enumerate(todos, 1):
            status = "✅" if todo.completed else "⬜"
            lines.append(f"{i}. {status} {todo.task}")
        return "\n".join(lines)

    async def _mark_done(self, task: str) -> str:
        """标记任务完成"""
        # 查找任务（可以是完整匹配或部分匹配）
        todo = (
            self.db.query(Todo)
            .filter(
                Todo.session_id == self.session_id,
                Todo.task.contains(task),
                Todo.completed.is_(False),
            )
            .first()
        )

        if not todo:
            return f"错误：未找到未完成的任务 '{task}'"

        todo.completed = True
        todo.completed_at = datetime.now()
        self.db.commit()
        return f"已标记任务完成：{todo.task}"

    async def _clear_tasks(self) -> str:
        """清除所有任务"""
        deleted = self.db.query(Todo).filter(Todo.session_id == self.session_id).delete()
        self.db.commit()
        return f"已清除 {deleted} 个任务。"
