from typing import Any, Dict
from app.tools.base import AgentTool
from app.services import sandbox_service


class ListTool(AgentTool):
    """列出沙箱中所有文件的工具"""

    def __init__(self, user_id: int, session_id: str):
        self.user_id = user_id
        self.session_id = session_id

    @property
    def name(self) -> str:
        return "list"

    @property
    def description(self) -> str:
        return "列出沙箱中的所有文件。无需参数。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def execute(self) -> str:
        """列出文件"""
        try:
            files = await sandbox_service.list_files(self.user_id, self.session_id)
            if not files:
                return "沙箱为空，没有文件。"
            return "沙箱文件列表：\n" + "\n".join(f"- {file}" for file in files)
        except Exception as e:
            return f"列出文件时出错：{str(e)}"
