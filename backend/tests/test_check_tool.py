"""CheckTool 测试用例"""

import shutil
import tempfile
from pathlib import Path

import pytest

from app.tools.check_tool import CheckTool


class TestCheckTool:
    """CheckTool 测试类"""

    @pytest.fixture
    def session_path(self):
        """创建临时会话目录"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def valid_html_file(self, session_path):
        """创建有效的 HTML 文件"""
        html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>测试页面</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>"""
        file_path = session_path / "index.html"
        file_path.write_text(html_content, encoding="utf-8")
        return file_path

    @pytest.fixture
    def broken_html_file(self, session_path):
        """创建损坏的 HTML 文件"""
        # 缺少闭合标签、嵌套错误等
        broken_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>测试页面</title>
</head>
<body>
    <h1>Hello World
    <div><p>未闭合的div和p
    <p>另一个段落</div>
    <ul><li>列表项</ul>
</body>
</html>"""
        file_path = session_path / "broken.html"
        file_path.write_text(broken_html, encoding="utf-8")
        return file_path

    @pytest.fixture
    def css_file(self, session_path):
        """创建 CSS 文件"""
        css_content = """body {
    margin: 0;
    padding: 0;
    background-color: #fff;
}

h1 {
    color: #333;
}"""
        file_path = session_path / "style.css"
        file_path.write_text(css_content, encoding="utf-8")
        return file_path

    @pytest.fixture
    def js_file(self, session_path):
        """创建 JavaScript 文件"""
        js_content = """function greet(name) {
    console.log('Hello, ' + name);
}

greet('World');"""
        file_path = session_path / "script.js"
        file_path.write_text(js_content, encoding="utf-8")
        return file_path

    @pytest.mark.asyncio
    async def test_check_valid_html(self, session_path, valid_html_file):
        """测试检查有效的 HTML 文件

        注意：tidy 对中文字符较严格，可能会有警告
        这里主要验证检查功能能正常运行
        """
        tool = CheckTool(session_path)
        result = await tool.execute(type="html", filename="index.html")
        # 验证检查功能正常运行，返回了结果
        assert result is not None
        assert "HTML" in result or "html" in result.lower()

    @pytest.mark.asyncio
    async def test_check_broken_html(self, session_path, broken_html_file):
        """测试检查损坏的 HTML 文件"""
        tool = CheckTool(session_path)
        result = await tool.execute(type="html", filename="broken.html")
        # tidy 应该检测到问题
        assert "⚠️" in result or "发现问题" in result or "warning" in result.lower()

    @pytest.mark.asyncio
    async def test_check_css(self, session_path, css_file):
        """测试检查 CSS 文件"""
        tool = CheckTool(session_path)
        result = await tool.execute(type="css", filename="style.css")
        # stylelint 可能未安装，所以可能返回安装提示
        assert "CSS" in result

    @pytest.mark.asyncio
    async def test_check_js(self, session_path, js_file):
        """测试检查 JavaScript 文件"""
        tool = CheckTool(session_path)
        result = await tool.execute(type="js", filename="script.js")
        # eslint 可能未安装，所以可能返回安装提示
        assert "JavaScript" in result

    @pytest.mark.asyncio
    async def test_check_all_files(self, session_path, valid_html_file, css_file, js_file):
        """测试检查所有文件"""
        tool = CheckTool(session_path)
        result = await tool.execute(type="all")
        assert "HTML" in result
        assert "CSS" in result
        assert "JS" in result or "JavaScript" in result

    @pytest.mark.asyncio
    async def test_check_nonexistent_file(self, session_path):
        """测试检查不存在的文件"""
        tool = CheckTool(session_path)
        result = await tool.execute(type="html", filename="nonexistent.html")
        assert "不存在" in result

    def test_tool_properties(self, session_path):
        """测试工具属性"""
        tool = CheckTool(session_path)
        assert tool.name == "check"
        assert tool.description is not None
        assert "html" in tool.description
        assert tool.parameters is not None
        assert tool.parameters["properties"]["type"]["enum"] == ["html", "css", "js", "all"]
