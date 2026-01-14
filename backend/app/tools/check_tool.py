import logging
import subprocess
from pathlib import Path
from typing import Any

from app.tools.base import AgentTool

logger = logging.getLogger(__name__)

# 默认文件映射
_DEFAULT_FILES = {
    "html": "index.html",
    "css": "style.css",
    "js": "script.js"
}

# 工具安装提示
_INSTALL_HINTS = {
    "html": "brew install tidy-html5 (macOS) 或 apt-get install tidy (Linux)",
    "css": "npm install -g stylelint",
    "js": "npm install -g eslint"
}


def _check_command_exists(command: str) -> bool:
    """检查命令是否存在。"""
    try:
        subprocess.run(
            ["which", command],
            capture_output=True,
            check=True,
            timeout=5
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _run_subprocess(command: list, timeout: int = 10) -> subprocess.CompletedProcess:
    """运行子进程并捕获输出。"""
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout
    )


class CheckTool(AgentTool):
    """代码质量检查工具（HTML/CSS/JavaScript）。"""

    def __init__(self, session_path: Path):
        self.session_path = session_path
        self._tools_available = None  # 延迟初始化

    @property
    def name(self) -> str:
        return "check"

    @property
    def description(self) -> str:
        return """检查代码质量。

支持以下检查类型：
- html: 检查HTML语法（使用 tidy）
- css: 检查CSS语法（使用 stylelint）
- js: 检查JavaScript语法（使用 eslint）

参数示例：
{"type": "html", "filename": "index.html"}
{"type": "css", "filename": "style.css"}
{"type": "js", "filename": "script.js"}
{"type": "all"}  # 检查所有默认文件

注意：如果检查工具未安装，会返回提示信息而不会报错
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["html", "css", "js", "all"],
                    "description": "检查类型"
                },
                "filename": {
                    "type": "string",
                    "description": "文件名（当type为all时可选）"
                }
            },
            "required": ["type"]
        }

    def _get_tools_available(self) -> dict[str, bool]:
        """获取可用工具状态（延迟初始化）。"""
        if self._tools_available is None:
            self._tools_available = {
                "html": _check_command_exists("tidy"),
                "css": _check_command_exists("stylelint"),
                "js": _check_command_exists("eslint")
            }
        return self._tools_available

    async def execute(self, type: str, filename: str = None) -> str:
        """执行代码检查。"""
        tools_available = self._get_tools_available()

        if type == "all":
            return await self._check_all(filename, tools_available)

        if not tools_available.get(type):
            return self._format_unavailable_message(type)

        return await self._run_check(type, filename)

    async def _check_all(self, filename: str, tools_available: dict[str, bool]) -> str:
        """检查所有文件类型。"""
        results = []
        default_files = {
            check_type: filename or default_name
            for check_type, default_name in _DEFAULT_FILES.items()
        }

        for check_type in ["html", "css", "js"]:
            if tools_available[check_type]:
                result = await self._run_check(check_type, default_files[check_type])
                if result:
                    results.append(f"**{check_type.upper()}检查**:\n{result}")
            else:
                results.append(
                    f"**{check_type.upper()}检查**: 检查工具未安装，跳过此项检查"
                )

        return "\n\n".join(results) if results else "没有可用的检查工具"

    def _format_unavailable_message(self, check_type: str) -> str:
        """格式化工具不可用提示。"""
        hint = _INSTALL_HINTS.get(check_type, "")
        return (
            f"{check_type.upper()}检查工具未安装。\n"
            f"如需使用此功能，请先安装：\n"
            f"- {hint}"
        )

    async def _run_check(self, check_type: str, filename: str = None) -> str:
        """运行具体检查。"""
        try:
            check_method = getattr(self, f"_check_{check_type}")
            return await check_method(filename)
        except Exception as e:
            logger.error(f"Check failed for {check_type}: {e}")
            return f"检查执行失败: {str(e)}"

    def _get_file_path(self, filename: str, check_type: str) -> Path:
        """获取文件路径，使用默认文件名如果未提供。"""
        if not filename:
            filename = _DEFAULT_FILES.get(check_type, "")
        return self.session_path / filename

    async def _check_html(self, filename: str = None) -> str:
        """检查 HTML。"""
        file_path = self._get_file_path(filename, "html")

        if not file_path.exists():
            return f"⚠️ 文件不存在: {filename or _DEFAULT_FILES['html']}"

        result = _run_subprocess(["tidy", "-q", "-e", str(file_path)])

        if result.returncode in (0, 1):
            # tidy 返回 1 表示有警告但可以解析
            if not result.stderr:
                return "✅ HTML检查通过，无语法错误"
            return f"⚠️ HTML发现问题:\n{result.stderr}"

        return f"❌ HTML检查失败:\n{result.stderr}"

    async def _check_css(self, filename: str = None) -> str:
        """检查 CSS。"""
        file_path = self._get_file_path(filename, "css")

        if not file_path.exists():
            return f"⚠️ 文件不存在: {filename or _DEFAULT_FILES['css']}"

        result = _run_subprocess(["stylelint", str(file_path)])

        if result.returncode == 0:
            return "✅ CSS检查通过"
        return f"⚠️ CSS发现问题:\n{result.stdout}"

    async def _check_js(self, filename: str = None) -> str:
        """检查 JavaScript。"""
        file_path = self._get_file_path(filename, "js")

        if not file_path.exists():
            return f"⚠️ 文件不存在: {filename or _DEFAULT_FILES['js']}"

        result = _run_subprocess(["eslint", str(file_path)])

        if result.returncode == 0:
            return "✅ JavaScript检查通过"
        return f"⚠️ JavaScript发现问题:\n{result.stdout}"
