import asyncio
import shlex
from pathlib import Path
from typing import Any

from app.tools.base import AgentTool


class BashTool(AgentTool):
    """执行bash命令的工具（受限于沙箱目录）"""

    # 允许的命令白名单
    ALLOWED_COMMANDS = {
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "mkdir",
        "rm",
        "mv",
        "cp",
        "pwd",
        "echo",
    }

    def __init__(self, session_path: Path, timeout: int = 30):
        self.session_path = session_path
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            "执行bash命令（仅限沙箱内操作）。"
            "支持的命令：ls（列出文件）, cat（查看文件）, grep（搜索）, "
            "mkdir（创建目录）, rm（删除）, mv（移动）, cp（复制）等。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的bash命令，例如：ls -la, cat index.html",
                }
            },
            "required": ["command"],
        }

    async def execute(self, command: str) -> str:
        """执行bash命令"""
        try:
            # 解析命令
            parts = shlex.split(command)
            if not parts:
                return "错误：命令为空"

            # 检查命令是否在白名单中
            base_command = parts[0]
            if base_command not in self.ALLOWED_COMMANDS:
                allowed = ", ".join(self.ALLOWED_COMMANDS)
                return f"错误：不允许执行命令 '{base_command}'。仅支持：{allowed}"

            # 确保沙箱目录存在
            self.session_path.mkdir(parents=True, exist_ok=True)

            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *parts,
                cwd=str(self.session_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except TimeoutError:
                process.kill()
                return f"错误：命令执行超时（>{self.timeout}秒）"

            # 返回结果
            output = stdout.decode("utf-8", errors="ignore")
            error = stderr.decode("utf-8", errors="ignore")

            if process.returncode != 0:
                return f"命令执行失败（退出码: {process.returncode}）\n{error}"

            return output if output else "命令执行成功（无输出）"

        except Exception as e:
            return f"执行bash命令时出错：{str(e)}"
