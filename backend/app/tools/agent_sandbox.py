from pathlib import Path
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.tools.base import AgentTool
from app.tools.bash_tool import BashTool
from app.tools.list_tool import ListTool
from app.tools.read_tool import ReadTool
from app.tools.write_tool import WriteTool
from app.tools.todo_tool import TodoTool
from app.tools.check_tool import CheckTool
from app.services.sandbox_service import get_sandbox_path


class AgentSandbox:
    """管理工具执行的沙箱环境"""

    def __init__(self, session_id: str, user_id: int, db: Session):
        self.session_id = session_id
        self.user_id = user_id
        self.db = db
        self.session_path = get_sandbox_path(user_id, session_id)
        self.tools = self._init_tools()

    def _init_tools(self) -> Dict[str, AgentTool]:
        """初始化所有可用工具"""
        return {
            "bash": BashTool(self.session_path),
            "list": ListTool(self.user_id, self.session_id),
            "read": ReadTool(self.user_id, self.session_id),
            "write": WriteTool(self.user_id, self.session_id),
            "todo": TodoTool(self.session_id, self.db),
            "check": CheckTool(self.session_path)
        }

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """获取所有工具的OpenAI格式定义"""
        return [tool.to_openai_tool() for tool in self.tools.values()]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """执行指定的工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            执行结果字符串

        Raises:
            ValueError: 如果工具不存在
        """
        if tool_name not in self.tools:
            available = ", ".join(self.tools.keys())
            raise ValueError(
                f"未知的工具：{tool_name}。可用工具：{available}"
            )

        tool = self.tools[tool_name]
        return await tool.execute(**arguments)
