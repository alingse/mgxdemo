from typing import Any

from app.services import sandbox_service
from app.tools.base import AgentTool


class ReadTool(AgentTool):
    """读取文件内容的工具"""

    def __init__(self, user_id: int, session_id: str):
        self.user_id = user_id
        self.session_id = session_id

    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "读取沙箱中文件的内容。需要提供文件名。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "要读取的文件名，例如：index.html, style.css",
                }
            },
            "required": ["filename"],
        }

    async def execute(self, filename: str) -> str:
        """读取文件"""
        try:
            content = await sandbox_service.read_file(self.user_id, self.session_id, filename)
            return f"文件 {filename} 的内容：\n\n{content}"
        except FileNotFoundError:
            return f"错误：文件 {filename} 不存在。"
        except ValueError as e:
            return f"错误：{str(e)}"
        except Exception as e:
            return f"读取文件时出错：{str(e)}"
