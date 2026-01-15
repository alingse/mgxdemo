import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.todo import TodoSnapshot
from app.tools.base import AgentTool


class TodoWriteTool(AgentTool):
    """TODO 写入工具 - 模仿 Claude TodoWrite"""

    def __init__(self, session_id: str, db: Session):
        self.session_id = session_id
        self.db = db

    @property
    def name(self) -> str:
        return "todo_write"

    @property
    def description(self) -> str:
        return (
            "任务列表管理工具。用于记录和追踪任务进度。\n"
            "每次调用会完全替换当前 session 的 todo 列表。\n"
            "状态类型：pending（待处理）、in_progress（进行中）、completed（已完成）"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "完整的任务列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "任务描述（祈使句形式，如：创建 HTML 结构）",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "任务状态",
                            },
                            "activeForm": {
                                "type": "string",
                                "description": "任务的进行时形式（如：正在创建 HTML 结构）",
                            },
                        },
                        "required": ["content", "status", "activeForm"],
                    },
                }
            },
            "required": ["todos"],
        }

    async def execute(self, todos: list[dict]) -> str:
        """执行 TODO 写入"""
        try:
            # 验证 todos 格式
            if not isinstance(todos, list):
                return "错误：todos 必须是数组"

            # 序列化为 JSON
            todos_json = json.dumps(todos, ensure_ascii=False)

            # 查找现有快照
            snapshot = (
                self.db.query(TodoSnapshot)
                .filter(TodoSnapshot.session_id == self.session_id)
                .first()
            )

            if snapshot:
                # 更新现有快照
                snapshot.todos_json = todos_json
            else:
                # 创建新快照
                snapshot = TodoSnapshot(session_id=self.session_id, todos_json=todos_json)
                self.db.add(snapshot)

            self.db.commit()

            # 返回结构化响应
            total = len(todos)
            completed = sum(1 for t in todos if t.get("status") == "completed")
            in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
            pending = sum(1 for t in todos if t.get("status") == "pending")

            response = {
                "todos": todos,
                "total": total,
                "completed": completed,
                "in_progress": in_progress,
                "pending": pending,
            }

            return json.dumps(response, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"错误：{str(e)}"
