import os
import aiofiles
from pathlib import Path
from typing import Dict, List, Optional
from app.config import get_settings
import re

settings = get_settings()


class SandboxService:
    """Service for managing sandbox files."""

    def __init__(self):
        self.base_dir = Path(settings.sandbox_base_dir)
        self.max_file_size = settings.max_file_size_mb * 1024 * 1024
        self.max_sandbox_size = settings.max_sandbox_size_mb * 1024 * 1024

    def _get_sandbox_path(self, user_id: int, session_id: str) -> Path:
        """Get the sandbox directory path for a user session."""
        return self.base_dir / str(user_id) / str(session_id)

    def _validate_filename(self, filename: str) -> bool:
        """Validate filename to prevent path traversal attacks."""
        # Only allow alphanumeric, dash, underscore, and dot
        return bool(re.match(r'^[\w\-\.]+$', filename)) and filename not in ('.', '..')

    def _get_sandbox_size(self, sandbox_path: Path) -> int:
        """Calculate total size of all files in the sandbox directory."""
        if not sandbox_path.exists():
            return 0

        total_size = 0
        for file_path in sandbox_path.iterdir():
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size

    async def initialize_sandbox(self, user_id: int, session_id: str) -> None:
        """Initialize a new sandbox with default files."""
        sandbox_path = self._get_sandbox_path(user_id, session_id)
        sandbox_path.mkdir(parents=True, exist_ok=True)

        # Create default files
        default_files = {
            "index.html": """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Sandbox</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="app">
        <h1>Hello, World!</h1>
        <p>This is your sandbox. Ask AI to create something amazing!</p>
    </div>
    <script src="script.js"></script>
</body>
</html>
""",
            "script.js": """// Your JavaScript code here
console.log('Sandbox initialized!');
""",
            "style.css": """/* Your CSS code here */
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}

#app {
    max-width: 800px;
    margin: 0 auto;
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

h1 {
    color: #333;
}
"""
        }

        for filename, content in default_files.items():
            await self.write_file(user_id, session_id, filename, content)

    async def list_files(self, user_id: int, session_id: str) -> List[str]:
        """List all files in the sandbox."""
        sandbox_path = self._get_sandbox_path(user_id, session_id)
        if not sandbox_path.exists():
            return []

        files = []
        for file_path in sandbox_path.iterdir():
            if file_path.is_file():
                files.append(file_path.name)
        return sorted(files)

    async def read_file(self, user_id: int, session_id: str, filename: str) -> str:
        """Read a file from the sandbox."""
        if not self._validate_filename(filename):
            raise ValueError(f"Invalid filename: {filename}")

        file_path = self._get_sandbox_path(user_id, session_id) / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename}")

        async with aiofiles.open(file_path, mode='r') as f:
            return await f.read()

    async def write_file(self, user_id: int, session_id: str, filename: str, content: str) -> None:
        """Write a file to the sandbox."""
        if not self._validate_filename(filename):
            raise ValueError(f"Invalid filename: {filename}")

        # Check file size
        content_size = len(content.encode('utf-8'))
        if content_size > self.max_file_size:
            raise ValueError(f"File size exceeds limit of {settings.max_file_size_mb}MB")

        sandbox_path = self._get_sandbox_path(user_id, session_id)
        sandbox_path.mkdir(parents=True, exist_ok=True)

        # Check total sandbox size before writing
        current_size = self._get_sandbox_size(sandbox_path)
        file_path = sandbox_path / filename

        # If file exists, subtract its current size
        if file_path.exists():
            current_size -= file_path.stat().st_size

        # Add new file size
        if current_size + content_size > self.max_sandbox_size:
            size_mb = (current_size + content_size) / (1024 * 1024)
            raise ValueError(
                f"Sandbox size would exceed limit of {settings.max_sandbox_size_mb}MB "
                f"(current: {current_size / (1024 * 1024):.2f}MB, "
                f"new file: {content_size / (1024 * 1024):.2f}MB)"
            )

        async with aiofiles.open(file_path, mode='w') as f:
            await f.write(content)

    async def delete_file(self, user_id: int, session_id: str, filename: str) -> None:
        """Delete a file from the sandbox."""
        if not self._validate_filename(filename):
            raise ValueError(f"Invalid filename: {filename}")

        file_path = self._get_sandbox_path(user_id, session_id) / filename
        if file_path.exists():
            file_path.unlink()

    async def get_all_files(self, user_id: int, session_id: str) -> Dict[str, str]:
        """Get all files and their contents."""
        files = {}
        for filename in await self.list_files(user_id, session_id):
            try:
                files[filename] = await self.read_file(user_id, session_id, filename)
            except Exception:
                pass
        return files

    async def update_files(self, user_id: int, session_id: str, files: Dict[str, str]) -> None:
        """Update multiple files in the sandbox."""
        for filename, content in files.items():
            await self.write_file(user_id, session_id, filename, content)

    def get_preview_url(self, user_id: int, session_id: str) -> str:
        """Get the URL for previewing the sandbox."""
        return f"/api/sessions/{session_id}/sandbox/preview"

    async def delete_sandbox(self, user_id: int, session_id: str) -> None:
        """Delete the entire sandbox directory."""
        sandbox_path = self._get_sandbox_path(user_id, session_id)
        if sandbox_path.exists():
            for file_path in sandbox_path.iterdir():
                if file_path.is_file():
                    file_path.unlink()
            sandbox_path.rmdir()
            parent_dir = sandbox_path.parent
            if parent_dir.exists() and not any(parent_dir.iterdir()):
                parent_dir.rmdir()


def get_sandbox_service() -> SandboxService:
    """Get the sandbox service instance."""
    return SandboxService()
