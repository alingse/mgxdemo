"""Sandbox Tools 测试用例 - Read, List, Write 工具的完整测试"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from app.tools.list_tool import ListTool
from app.tools.read_tool import ReadTool
from app.tools.write_tool import WriteTool
from app.services.sandbox_service import (
    get_sandbox_service,
    initialize_sandbox,
    read_file,
    write_file,
    list_files
)


class TestSandboxServiceModuleFunctions:
    """测试 sandbox_service 模块级别的便捷函数"""

    @pytest.fixture
    def temp_sandbox_dir(self):
        """创建临时沙箱目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_user_id(self):
        """测试用户 ID"""
        return 999

    @pytest.fixture
    def test_session_id(self):
        """测试会话 ID"""
        return "test_session_abc123"

    @pytest.fixture
    def sandbox_path(self, temp_sandbox_dir, test_user_id, test_session_id):
        """设置沙箱路径并确保目录存在"""
        # 临时覆盖沙箱配置
        from app.config import get_settings
        from unittest.mock import patch

        settings = get_settings()
        original_base_dir = settings.sandbox_base_dir

        with patch.object(settings, 'sandbox_base_dir', temp_sandbox_dir):
            sandbox_service = get_sandbox_service()
            sandbox_path = sandbox_service._get_sandbox_path(test_user_id, test_session_id)
            sandbox_path.mkdir(parents=True, exist_ok=True)
            yield sandbox_path

        # 恢复原始配置
        settings.sandbox_base_dir = original_base_dir

    @pytest.mark.asyncio
    async def test_module_level_write_file(self, sandbox_path, test_user_id, test_session_id):
        """测试模块级别 write_file 函数"""
        test_content = "<h1>Test Content</h1>"
        result = await write_file(test_user_id, test_session_id, "test.html", test_content)

        # 验证文件被创建
        file_path = sandbox_path / "test.html"
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == test_content

    @pytest.mark.asyncio
    async def test_module_level_read_file(self, sandbox_path, test_user_id, test_session_id):
        """测试模块级别 read_file 函数"""
        test_content = "console.log('test');"
        file_path = sandbox_path / "test.js"
        file_path.write_text(test_content, encoding="utf-8")

        content = await read_file(test_user_id, test_session_id, "test.js")
        assert content == test_content

    @pytest.mark.asyncio
    async def test_module_level_list_files(self, sandbox_path, test_user_id, test_session_id):
        """测试模块级别 list_files 函数"""
        # 创建一些测试文件
        (sandbox_path / "index.html").write_text("<html></html>", encoding="utf-8")
        (sandbox_path / "style.css").write_text("body {}", encoding="utf-8")
        (sandbox_path / "script.js").write_text("console.log('test');", encoding="utf-8")

        files = await list_files(test_user_id, test_session_id)
        assert set(files) == {"index.html", "style.css", "script.js"}

    @pytest.mark.asyncio
    async def test_module_level_read_nonexistent_file(self, sandbox_path, test_user_id, test_session_id):
        """测试读取不存在的文件"""
        with pytest.raises(FileNotFoundError):
            await read_file(test_user_id, test_session_id, "nonexistent.html")


class TestReadTool:
    """ReadTool 工具测试"""

    @pytest.fixture
    def temp_sandbox_dir(self):
        """创建临时沙箱目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_user_id(self):
        return 1001

    @pytest.fixture
    def test_session_id(self):
        return "read_test_session"

    @pytest.fixture
    def sandbox_path(self, temp_sandbox_dir, test_user_id, test_session_id):
        """设置沙箱路径"""
        from app.config import get_settings
        from unittest.mock import patch

        settings = get_settings()

        with patch.object(settings, 'sandbox_base_dir', temp_sandbox_dir):
            sandbox_service = get_sandbox_service()
            sandbox_path = sandbox_service._get_sandbox_path(test_user_id, test_session_id)
            sandbox_path.mkdir(parents=True, exist_ok=True)
            yield sandbox_path

    @pytest.mark.asyncio
    async def test_read_existing_file(self, sandbox_path, test_user_id, test_session_id):
        """测试读取存在的文件"""
        test_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>"""
        (sandbox_path / "index.html").write_text(test_content, encoding="utf-8")

        tool = ReadTool(test_user_id, test_session_id)
        result = await tool.execute(filename="index.html")

        assert "文件 index.html 的内容" in result
        assert "<!DOCTYPE html>" in result
        assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, sandbox_path, test_user_id, test_session_id):
        """测试读取不存在的文件"""
        tool = ReadTool(test_user_id, test_session_id)
        result = await tool.execute(filename="nonexistent.html")

        assert "不存在" in result

    @pytest.mark.asyncio
    async def test_read_css_file(self, sandbox_path, test_user_id, test_session_id):
        """测试读取 CSS 文件"""
        css_content = """body {
    margin: 0;
    padding: 0;
    font-family: Arial, sans-serif;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}"""
        (sandbox_path / "style.css").write_text(css_content, encoding="utf-8")

        tool = ReadTool(test_user_id, test_session_id)
        result = await tool.execute(filename="style.css")

        assert "文件 style.css 的内容" in result
        assert "margin: 0;" in result
        assert "max-width: 1200px;" in result

    @pytest.mark.asyncio
    async def test_read_javascript_file(self, sandbox_path, test_user_id, test_session_id):
        """测试读取 JavaScript 文件"""
        js_content = """// Main application
function init() {
    console.log('App initialized');
    loadConfig();
}

function loadConfig() {
    return fetch('/config.json').then(r => r.json());
}

init();"""
        (sandbox_path / "app.js").write_text(js_content, encoding="utf-8")

        tool = ReadTool(test_user_id, test_session_id)
        result = await tool.execute(filename="app.js")

        assert "文件 app.js 的内容" in result
        assert "function init()" in result
        assert "loadConfig" in result

    @pytest.mark.asyncio
    async def test_read_file_with_special_characters(self, sandbox_path, test_user_id, test_session_id):
        """测试读取包含特殊字符的文件"""
        content = "测试中文内容 & Special <chars>"
        (sandbox_path / "test.txt").write_text(content, encoding="utf-8")

        tool = ReadTool(test_user_id, test_session_id)
        result = await tool.execute(filename="test.txt")

        assert "测试中文内容" in result
        assert "Special <chars>" in result

    @pytest.mark.asyncio
    async def test_read_file_with_invalid_filename(self, sandbox_path, test_user_id, test_session_id):
        """测试使用无效文件名（路径遍历攻击）"""
        tool = ReadTool(test_user_id, test_session_id)
        result = await tool.execute(filename="../../../etc/passwd")

        assert "错误" in result

    def test_read_tool_properties(self, test_user_id, test_session_id):
        """测试 ReadTool 的基本属性"""
        tool = ReadTool(test_user_id, test_session_id)

        assert tool.name == "read"
        assert tool.description is not None
        assert "读取" in tool.description or "文件" in tool.description
        assert tool.parameters is not None
        assert "filename" in tool.parameters["properties"]
        assert "filename" in tool.parameters["required"]


class TestListTool:
    """ListTool 工具测试"""

    @pytest.fixture
    def temp_sandbox_dir(self):
        """创建临时沙箱目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_user_id(self):
        return 2001

    @pytest.fixture
    def test_session_id(self):
        return "list_test_session"

    @pytest.fixture
    def sandbox_path(self, temp_sandbox_dir, test_user_id, test_session_id):
        """设置沙箱路径"""
        from app.config import get_settings
        from unittest.mock import patch

        settings = get_settings()

        with patch.object(settings, 'sandbox_base_dir', temp_sandbox_dir):
            sandbox_service = get_sandbox_service()
            sandbox_path = sandbox_service._get_sandbox_path(test_user_id, test_session_id)
            sandbox_path.mkdir(parents=True, exist_ok=True)
            yield sandbox_path

    @pytest.mark.asyncio
    async def test_list_multiple_files(self, sandbox_path, test_user_id, test_session_id):
        """测试列出多个文件"""
        files_to_create = [
            ("index.html", "<html></html>"),
            ("style.css", "body {}"),
            ("script.js", "console.log('test');"),
            ("README.md", "# Test Project")
        ]

        for filename, content in files_to_create:
            (sandbox_path / filename).write_text(content, encoding="utf-8")

        tool = ListTool(test_user_id, test_session_id)
        result = await tool.execute()

        assert "沙箱文件列表" in result
        assert "- index.html" in result
        assert "- style.css" in result
        assert "- script.js" in result
        assert "- README.md" in result

    @pytest.mark.asyncio
    async def test_list_empty_sandbox(self, sandbox_path, test_user_id, test_session_id):
        """测试列出空的沙箱"""
        tool = ListTool(test_user_id, test_session_id)
        result = await tool.execute()

        assert "空" in result or "没有文件" in result

    @pytest.mark.asyncio
    async def test_list_sorted_order(self, sandbox_path, test_user_id, test_session_id):
        """测试文件列表按字母顺序排列"""
        files = ["zebra.html", "apple.js", "middle.css"]
        for filename in files:
            (sandbox_path / filename).write_text("content", encoding="utf-8")

        tool = ListTool(test_user_id, test_session_id)
        result = await tool.execute()

        lines = result.split("\n")
        file_lines = [line for line in lines if line.startswith("- ")]

        # 验证按字母顺序排列
        assert file_lines[0] == "- apple.js"
        assert file_lines[1] == "- middle.css"
        assert file_lines[2] == "- zebra.html"

    def test_list_tool_properties(self, test_user_id, test_session_id):
        """测试 ListTool 的基本属性"""
        tool = ListTool(test_user_id, test_session_id)

        assert tool.name == "list"
        assert tool.description is not None
        assert "列表" in tool.description or "文件" in tool.description
        assert tool.parameters is not None
        assert tool.parameters["properties"] == {}
        assert tool.parameters["required"] == []


class TestWriteTool:
    """WriteTool 工具测试"""

    @pytest.fixture
    def temp_sandbox_dir(self):
        """创建临时沙箱目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_user_id(self):
        return 3001

    @pytest.fixture
    def test_session_id(self):
        return "write_test_session"

    @pytest.fixture
    def sandbox_path(self, temp_sandbox_dir, test_user_id, test_session_id):
        """设置沙箱路径"""
        from app.config import get_settings
        from unittest.mock import patch

        settings = get_settings()

        with patch.object(settings, 'sandbox_base_dir', temp_sandbox_dir):
            sandbox_service = get_sandbox_service()
            sandbox_path = sandbox_service._get_sandbox_path(test_user_id, test_session_id)
            sandbox_path.mkdir(parents=True, exist_ok=True)
            yield sandbox_path

    @pytest.mark.asyncio
    async def test_write_new_file(self, sandbox_path, test_user_id, test_session_id):
        """测试写入新文件"""
        html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>测试页面</title>
</head>
<body>
    <h1>你好，世界！</h1>
</body>
</html>"""

        tool = WriteTool(test_user_id, test_session_id)
        result = await tool.execute(filename="test.html", content=html_content)

        assert "成功写入" in result or "写入" in result
        assert "test.html" in result

        # 验证文件内容
        file_path = sandbox_path / "test.html"
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == html_content

    @pytest.mark.asyncio
    async def test_write_overwrite_existing_file(self, sandbox_path, test_user_id, test_session_id):
        """测试覆盖已存在的文件"""
        (sandbox_path / "config.json").write_text('{"old": "data"}', encoding="utf-8")

        new_content = '{"new": "data", "version": "2.0"}'
        tool = WriteTool(test_user_id, test_session_id)
        result = await tool.execute(filename="config.json", content=new_content)

        assert "成功写入" in result or "写入" in result

        # 验证文件被覆盖
        file_path = sandbox_path / "config.json"
        assert file_path.read_text(encoding="utf-8") == new_content

    @pytest.mark.asyncio
    async def test_write_css_file(self, sandbox_path, test_user_id, test_session_id):
        """测试写入 CSS 文件"""
        css_content = """/* 全局样式 */
:root {
    --primary-color: #3498db;
    --secondary-color: #2ecc71;
    --text-color: #333;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, sans-serif;
    color: var(--text-color);
}"""

        tool = WriteTool(test_user_id, test_session_id)
        result = await tool.execute(filename="styles.css", content=css_content)

        assert "成功写入" in result

        # 验证 CSS 内容
        file_path = sandbox_path / "styles.css"
        assert "--primary-color" in file_path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_write_javascript_file(self, sandbox_path, test_user_id, test_session_id):
        """测试写入 JavaScript 文件"""
        js_content = """// 应用配置
const CONFIG = {
    apiUrl: 'https://api.example.com',
    timeout: 5000,
    retries: 3
};

// 工具函数
async function fetchData(endpoint) {
    try {
        const response = await fetch(`${CONFIG.apiUrl}${endpoint}`);
        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

export { fetchData, CONFIG };"""

        tool = WriteTool(test_user_id, test_session_id)
        result = await tool.execute(filename="utils.js", content=js_content)

        assert "成功写入" in result

        # 验证 JavaScript 内容
        file_path = sandbox_path / "utils.js"
        assert "fetchData" in file_path.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_write_file_with_unicode(self, sandbox_path, test_user_id, test_session_id):
        """测试写入包含 Unicode 字符的文件"""
        content = "你好世界！Hello World! 🚀🎉\nПривет мир!\nمرحبا بالعالم"

        tool = WriteTool(test_user_id, test_session_id)
        result = await tool.execute(filename="unicode.txt", content=content)

        assert "成功写入" in result

        # 验证 Unicode 内容正确保存
        file_path = sandbox_path / "unicode.txt"
        assert file_path.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_write_large_file(self, sandbox_path, test_user_id, test_session_id):
        """测试写入较大的文件"""
        # 生成一个约 10KB 的 HTML 内容
        large_content = "<!DOCTYPE html><html><head><title>Large File</title></head><body>"
        for i in range(1000):
            large_content += f'<p>Paragraph {i}: Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>'
        large_content += "</body></html>"

        tool = WriteTool(test_user_id, test_session_id)
        result = await tool.execute(filename="large.html", content=large_content)

        assert "成功写入" in result
        assert len(result) > 0

        # 验证文件大小
        file_path = sandbox_path / "large.html"
        assert file_path.stat().st_size > 10000

    def test_write_tool_properties(self, test_user_id, test_session_id):
        """测试 WriteTool 的基本属性"""
        tool = WriteTool(test_user_id, test_session_id)

        assert tool.name == "write"
        assert tool.description is not None
        assert "创建" in tool.description or "写入" in tool.description or "覆盖" in tool.description
        assert tool.parameters is not None
        assert "filename" in tool.parameters["properties"]
        assert "content" in tool.parameters["properties"]
        assert set(tool.parameters["required"]) == {"filename", "content"}


class TestToolsIntegration:
    """工具集成测试 - 测试工具之间的配合"""

    @pytest.fixture
    def temp_sandbox_dir(self):
        """创建临时沙箱目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_user_id(self):
        return 4001

    @pytest.fixture
    def test_session_id(self):
        return "integration_test_session"

    @pytest.fixture
    def sandbox_path(self, temp_sandbox_dir, test_user_id, test_session_id):
        """设置沙箱路径"""
        from app.config import get_settings
        from unittest.mock import patch

        settings = get_settings()

        with patch.object(settings, 'sandbox_base_dir', temp_sandbox_dir):
            sandbox_service = get_sandbox_service()
            sandbox_path = sandbox_service._get_sandbox_path(test_user_id, test_session_id)
            sandbox_path.mkdir(parents=True, exist_ok=True)
            yield sandbox_path

    @pytest.mark.asyncio
    async def test_write_then_read_workflow(self, sandbox_path, test_user_id, test_session_id):
        """测试写入后读取的工作流"""
        original_content = "Original content for testing"
        write_tool = WriteTool(test_user_id, test_session_id)
        read_tool = ReadTool(test_user_id, test_session_id)

        # 写入文件
        write_result = await write_tool.execute(filename="workflow.txt", content=original_content)
        assert "成功写入" in write_result

        # 读取文件
        read_result = await read_tool.execute(filename="workflow.txt")
        assert "Original content for testing" in read_result

    @pytest.mark.asyncio
    async def test_list_write_read_workflow(self, sandbox_path, test_user_id, test_session_id):
        """测试列表、写入、读取的完整工作流"""
        list_tool = ListTool(test_user_id, test_session_id)
        write_tool = WriteTool(test_user_id, test_session_id)
        read_tool = ReadTool(test_user_id, test_session_id)

        # 初始列表应该是空的
        initial_list = await list_tool.execute()
        assert "空" in initial_list or "没有文件" in initial_list

        # 写入多个文件
        files = {
            "index.html": "<html><body>Home</body></html>",
            "about.html": "<html><body>About</body></html>",
            "style.css": "body { margin: 0; }"
        }

        for filename, content in files.items():
            await write_tool.execute(filename=filename, content=content)

        # 列出文件
        list_result = await list_tool.execute()
        for filename in files.keys():
            assert f"- {filename}" in list_result

        # 读取每个文件验证内容
        for filename, expected_content in files.items():
            read_result = await read_tool.execute(filename=filename)
            assert expected_content in read_result

    @pytest.mark.asyncio
    async def test_overwrite_workflow(self, sandbox_path, test_user_id, test_session_id):
        """测试覆盖文件的完整工作流"""
        write_tool = WriteTool(test_user_id, test_session_id)
        read_tool = ReadTool(test_user_id, test_session_id)

        # 写入初始内容
        v1_content = "Version 1 content"
        await write_tool.execute(filename="version.txt", content=v1_content)

        # 验证 v1 内容
        v1_read = await read_tool.execute(filename="version.txt")
        assert "Version 1 content" in v1_read

        # 覆盖为新版本
        v2_content = "Version 2 content - updated!"
        await write_tool.execute(filename="version.txt", content=v2_content)

        # 验证 v2 内容
        v2_read = await read_tool.execute(filename="version.txt")
        assert "Version 2 content" in v2_read
        assert "Version 1 content" not in v2_read
