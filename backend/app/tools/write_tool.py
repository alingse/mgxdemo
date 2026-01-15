from typing import Any

from app.services import sandbox_service
from app.tools.base import AgentTool


class WriteTool(AgentTool):
    """创建或修改文件的工具"""

    def __init__(self, user_id: int, session_id: str):
        self.user_id = user_id
        self.session_id = session_id

    @property
    def name(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return (
            "创建新文件或完全覆盖现有文件。"
            "注意：此操作会覆盖现有内容，请谨慎使用。建议先使用read工具查看现有内容。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "文件名，例如：index.html, style.css, script.js",
                },
                "content": {"type": "string", "description": "文件的完整内容"},
            },
            "required": ["filename", "content"],
        }

    async def execute(self, filename: str, content: str) -> str:
        """写入文件"""
        try:
            await sandbox_service.write_file(self.user_id, self.session_id, filename, content)
            return f"成功写入文件 {filename}（大小：{len(content)} 字节）"
        except ValueError as e:
            return f"错误：{str(e)}"
        except Exception as e:
            return f"写入文件时出错：{str(e)}"
