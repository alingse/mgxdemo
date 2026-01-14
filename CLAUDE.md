# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI Agent Sandbox - 一个提供 AI 驱动网页开发沙箱环境的 Web 应用。用户可以创建会话、与 AI 对话，并由 AI 修改隔离沙箱目录中的文件。

## 开发命令

本项目使用 `uv` 作为包管理器。

```bash
# 安装依赖（从项目根目录）
cd backend && uv sync

# 运行开发服务器（从 backend 目录）
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或者直接用 Python 运行
cd backend && python -m app.main
```

服务器运行后可访问：
- API 文档: `http://localhost:8000/docs`
- 健康检查: `http://localhost:8000/health`
- 根路径: `http://localhost:8000/`

## 架构

### 技术栈
- **后端**: FastAPI + Python 3.12+
- **数据库**: SQLite + SQLAlchemy ORM
- **认证**: JWT 令牌 + bcrypt 密码哈希
- **AI 提供商**: OpenAI、智谱 GLM-4（Anthropic 占位存在但未实现）
- **前端**: 来自 `backend/app/static/` 的静态 HTML/CSS/JS

### 目录结构

```
backend/
├── app/
│   ├── api/          # FastAPI 路由（auth, sessions, messages, sandbox）
│   ├── core/         # 核心依赖（安全、认证依赖）
│   ├── models/       # SQLAlchemy 模型（User, Session, Message）
│   ├── schemas/      # Pydantic 请求/响应验证模式
│   ├── services/     # 业务逻辑层
│   ├── static/       # 前端资源
│   ├── config.py     # Pydantic 配置
│   ├── database.py   # SQLAlchemy 设置
│   └── main.py       # FastAPI 应用入口
├── sandboxes/        # 用户沙箱目录（运行时创建）
└── pyproject.toml    # uv 项目配置
```

### 核心架构模式

**服务层模式**: 业务逻辑分离到 `app/services/` 中的服务：
- `ai_service.py` - AI 提供商抽象与工厂模式
- `sandbox_service.py` - 沙箱文件系统操作
- `auth_service.py` - 认证工具

**AI 服务抽象**:
- `AIService` 抽象基类定义 `chat()` 和 `modify_files()` 方法
- `OpenAIService` 和 `ZhipuService` 实现该接口
- `AIServiceFactory` 根据提供商名称创建实例
- OpenAI 和智谱都使用 OpenAI 客户端库（不同的 base URL）

**沙箱隔离**:
- 每个用户会话获得 `sandboxes/{user_id}/{session_id}/` 目录
- 文件名验证防止路径遍历（`_validate_filename`）
- 初始化时创建默认文件（index.html, script.js, style.css）

**依赖注入**:
- FastAPI 依赖注入数据库会话（`get_db`）
- 通过 JWT 令牌注入当前用户（`get_current_user`）

## 配置

创建 `.env` 文件（参考 `backend/.env.example` 模板）：

```bash
# 从 backend 目录复制模板
cd backend
cp .env.example .env
# 编辑 .env 文件，填入实际的 API 密钥
```

**AI 提供商**（至少配置一个）:
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`
- `ZHIPU_API_KEY`, `ZHIPU_BASE_URL`, `ZHIPU_MODEL`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`（占位，未实现）
- `DEFAULT_AI_PROVIDER`（默认: "zhipu"）

**应用配置**:
- `SECRET_KEY` - JWT 签名密钥（生产环境必须更改）
- `ALGORITHM` - JWT 算法（默认: "HS256"）
- `ACCESS_TOKEN_EXPIRE_MINUTES` - 令牌过期时间（默认: 30 分钟）
- `DATABASE_URL` - SQLite 路径（默认: sqlite:///./agent_sandbox.db）
- `SANDBOX_BASE_DIR` - 沙箱目录（默认: ./sandboxes）
- `MAX_SANDBOX_SIZE_MB` - 每个会话大小限制（默认: 100MB）
- `MAX_FILE_SIZE_MB` - 单个文件大小限制（默认: 1MB）

## 数据库模型

- **User**: id, username, email, hashed_password, created_at, updated_at
- **Session**: id (UUID hex string), user_id, title, created_at, updated_at
- **Message**: id, session_id (string, FK to Session.id), content, role (user/assistant/system), created_at

**注意**: Session.id 使用 UUID hex 格式的字符串（如 `12db3c516aae14608a5013905b8c189f`），而不是自增整数。这提供更好的 URL 美观性和安全性。

## API 端点

- `/api/auth/register` - 用户注册
- `/api/auth/login` - 获取 JWT 令牌
- `/api/sessions` - 创建/列出用户会话
- `/api/sessions/{id}` - 获取/删除会话（id 为 UUID hex 字符串）
- `/api/sessions/{id}/messages` - 创建/列出消息
- `/api/sessions/{id}/sandbox/files` - 列出沙箱文件
- `/api/sessions/{id}/sandbox/files/{filename}` - 读取/写入/删除文件
- `/api/sessions/{id}/sandbox/preview` - 预览沙箱 HTML（用于 iframe）
- `/api/sessions/{id}/sandbox/static/{filename}` - 获取沙箱静态资源
- `/app/{session_id}` - **独立预览页面**，只显示沙箱内容（可单独访问）
- `/static/app.html` - 主应用页面（左侧聊天 + 右侧预览）
- `/docs` - 交互式 API 文档

## 重要说明

- 根目录 `/backend/main.py` 是占位文件 - 实际应用入口在 `/backend/app/main.py`
- CORS 配置允许所有来源（`allow_origins=["*"]`）- 不适合生产环境
- 数据库在启动时通过 `@app.on_event("startup")` 自动初始化
- Anthropic AI 提供商在 config 中定义但未在 `ai_service.py` 中实现
- 沙箱中的所有文件操作使用异步 `aiofiles` 实现非阻塞 I/O

### 核心功能实现

**智能文件修改触发**（messages.py:118-159）：
- 系统自动检测用户消息中的关键词（"创建"、"做一个"、"修改"等）
- 检测到关键词后自动调用 AI 的 `modify_files` 方法
- 无需 AI 输出特殊标记，提高可靠性
- 文件更新后会添加系统消息通知用户

**沙箱预览资源处理**（sandbox.py:105-142）：
- preview 端点会读取 index.html 并注入 `<base>` 标签
- 资源路径自动指向 `/api/sessions/{id}/sandbox/static/`
- 确保 CSS/JS 文件能正确加载到 iframe 中

**沙箱大小限制**（sandbox_service.py:28-37, 105-136）：
- `_get_sandbox_size` 方法计算目录总大小
- `write_file` 方法在写入前检查是否超过 `MAX_SANDBOX_SIZE_MB`
- 超限时返回详细错误信息（当前大小、新文件大小、限制值）

### 沙箱预览架构

**设计原则：安全性优先，使用 iframe 隔离用户代码**

本项目采用 **iframe 方案**来渲染用户生成的沙箱内容，而不是直接渲染到主页面中。这是经过仔细权衡后的架构决策。

---

#### 为什么选择 iframe 方案？

**核心原因：安全性**

用户代码可能包含恶意脚本，例如：
```javascript
// 用户代码中可能包含：
document.cookie;              // 读取 cookies
localStorage.getItem('token'); // 窃取认证令牌
document.querySelector('#secret').value; // 窃取敏感信息
```

使用 iframe 可以确保：
- ✅ **脚本隔离** - 用户 JavaScript 无法访问主应用的 DOM、localStorage、cookies
- ✅ **样式隔离** - 用户 CSS 不会影响主界面
- ✅ **XSS 保护** - 跨站脚本攻击只影响 iframe 内部
- ✅ **同源策略保护** - iframe 内的代码被限制在沙箱上下文中

---

#### 架构对比

| 方案 | 优点 | 缺点 | 是否采用 |
|------|------|------|---------|
| **iframe 方案** | 安全性高、样式隔离、实现简单 | 跨域通信复杂、高度自适应困难 | ✅ 采用 |
| **直接渲染 + Shadow DOM** | 用户体验好、移动端友好 | 样式冲突风险、脚本安全风险、兼容性问题 | ❌ 不采用 |
| **直接渲染 + Header** | URL 简洁 | 需要复杂的 fetch 拦截器、安全性低 | ❌ 不采用 |

**iframe 方案的问题及缓解：**
- ❌ 跨域通信 → 使用 `postMessage` API
- ❌ 高度自适应 → 使用 JS 计算并设置 iframe 高度
- ❌ 移动端体验 → 添加响应式 meta 标签和触摸事件处理
- ❌ 调试复杂 → 使用浏览器 DevTools 的上下文切换功能

---

#### 具体实现架构

**1. 工作台预览（`/chat/{session_id}`）**

```
/chat/{session_id}
├── 左侧：聊天区域（25%）
│   ├── 会话列表
│   ├── 消息历史
│   └── 输入框
└── 右侧：预览区域（75%）
    └── iframe src="/api/sessions/{session_id}/sandbox/preview"
         ├── index.html（注入 <base> 标签）
         └── 静态资源通过 /api/sessions/{session_id}/sandbox/static/
```

**2. 独立预览页面（`/app/{session_id}`）**

```
/app/{session_id}
├── 容器页面
│   ├── Header（标题、返回按钮、工具栏）
│   ├── Toolbar（刷新、全屏、查看代码等）
│   └── iframe src="/api/sessions/{session_id}/sandbox/preview"
```

**实现要点：**
- 使用 `sandbox` 属性限制 iframe 权限：`<iframe sandbox="allow-scripts allow-same-origin allow-forms">`
- 容器页面提供友好的 UI（标题、操作按钮）
- iframe 内容完全隔离，无法访问主页面

---

#### 静态资源加载机制

**问题**：用户代码中的 `<link href="style.css">` 和 `<script src="script.js">` 如何正确加载？

**解决方案**：使用 `<base>` 标签重写资源路径

```python
# sandbox.py:106-142
@router.get("/preview")
async def preview_sandbox(session_id: str, current_user: User, db: Session):
    # 读取 index.html
    html_content = await f.read()

    # 注入 base 标签，使相对路径指向正确的端点
    base_tag = f'<base href="/api/sessions/{session_id}/sandbox/static/">'

    # 在 <head> 后插入 base 标签
    html_content = html_content.replace('<head>', f'<head>\n    {base_tag}', 1)

    return HTMLResponse(content=html_content)
```

**结果**：
- 用户代码：`<link rel="stylesheet" href="style.css">`
- 实际加载：`/api/sessions/{session_id}/sandbox/static/style.css`
- 无需修改用户代码，自动处理资源路径

---

#### 为什么不使用 Header 传递 session_id？

有建议使用 HTTP Header（如 `x-app-id: session_id`）而非 URL 路径，但经分析：

| 方案 | 优点 | 缺点 |
|------|------|------|
| **URL 路径**（当前） | 直观、缓存友好、支持浏览器前进后退 | URL 稍长 |
| **HTTP Header** | URL 简洁 | 需要 fetch 拦截器、浏览器缓存失效、代码复杂度高 |

**结论**：URL 路径方案更简单可靠，继续采用。

---

#### 安全加固措施

1. **iframe sandbox 属性**：限制 iframe 权限，防止弹出窗口、表单提交等危险操作
2. **Content-Security-Policy**：配置 CSP header 限制外部资源加载
3. **文件名验证**：`_validate_filename()` 防止路径遍历攻击
4. **大小限制**：`MAX_SANDBOX_SIZE_MB` 和 `MAX_FILE_SIZE_MB` 防止资源耗尽
5. **认证检查**：所有沙箱端点都需要 JWT 令牌验证

---

#### 扩展性考虑

**未来可能的优化**：
- 添加 `postMessage` 通信，支持主页面与 iframe 双向通信
- 实现自适应高度，消除 iframe 滚动条
- 添加实时热重载，文件修改后自动刷新 iframe
- 支持多个预览窗口（桌面、移动端并排预览）

**不建议的改变**：
- ❌ 移除 iframe，改用直接渲染（安全性大幅下降）
- ❌ 使用 Shadow DOM 替代 iframe（兼容性和安全问题）
- ❌ 允许用户上传任意 HTML 文件（XSS 风险）

---

## AI 交互规范

**与模型交互时使用中文**。当编写与 AI 服务相关的代码（如 system prompt、用户消息模板等）时，应使用中文以保持与项目主要用户群体的一致性。`ZhipuService` 中的 `modify_files` 方法已使用中文 prompt，新建相关功能时应遵循此规范。
