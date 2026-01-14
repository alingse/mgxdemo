# AI 执行进度追踪功能 - 实现总结

## 功能概述

本功能为 AI Agent Sandbox 添加了**实时执行进度追踪**能力，让 C 端用户可以实时查看 AI 的思考过程、工具调用和执行结果。所有进度数据都持久化到数据库中，支持离线查询和历史记录。

## 实现架构

### 1. 数据库层

#### 新增模型：`AgentExecutionStep`

```python
class AgentExecutionStep(Base):
    """单次 AI 回复的执行步骤记录"""

    # 关联信息
    session_id: str        # 会话ID
    message_id: int        # 关联的助手消息ID
    user_id: int           # 用户ID

    # 执行信息
    iteration: int         # 第几轮循环（1-10）
    status: ExecutionStatus # 执行状态（thinking/tool_calling/tool_executing/completed等）

    # 思考内容（DeepSeek reasoning_content）
    reasoning_content: str # AI 的思考过程

    # 工具调用信息
    tool_name: str         # 工具名称（write/read/bash等）
    tool_arguments: dict   # 工具参数（JSON）
    tool_call_id: str      # 工具调用ID
    tool_result: str       # 工具执行结果
    tool_error: str        # 工具执行错误

    # 进度信息
    progress: float        # 进度百分比（0-100）
    created_at: datetime   # 创建时间
    updated_at: datetime   # 更新时间
```

#### 关联关系

```
Session (会话)
  └── Message (消息列表)
       ├── User Message 1
       ├── Assistant Message 2 ← 关联多个 AgentExecutionStep
       │    ├── Step 1: THINKING (iteration=1, progress=10%)
       │    ├── Step 2: TOOL_CALLING (tool=write, progress=20%)
       │    ├── Step 3: TOOL_EXECUTING (tool=write, progress=25%)
       │    ├── Step 4: TOOL_COMPLETED (tool=write, result="...", progress=30%)
       │    ├── Step 5: THINKING (iteration=2, progress=35%)
       │    └── Step 6: COMPLETED (progress=100%)
       └── User Message 3
```

### 2. 后端 API 层

#### 修改：`messages.py`

在 `create_message` 端点的 agent loop 中，每个关键步骤都会保存进度：

```python
# 1. 创建空的助手消息（用于关联执行步骤）
assistant_message = Message(...)
db.add(assistant_message)
db.commit()

# 2. Agent Loop 中保存每个步骤
while iteration < max_iterations:
    # 保存思考状态
    _save_execution_step(status=ExecutionStatus.THINKING, ...)

    # 调用 AI
    response, tool_calls, reasoning = await ai_service.chat_with_tools(...)

    # 保存工具调用状态
    for tool_call in tool_calls:
        _save_execution_step(status=ExecutionStatus.TOOL_CALLING, ...)

    # 保存工具执行状态
    for tool_call in tool_calls:
        _save_execution_step(status=ExecutionStatus.TOOL_EXECUTING, ...)
        result = await execute_tool(...)
        _save_execution_step(status=ExecutionStatus.TOOL_COMPLETED, ...)

# 3. 保存最终完成状态
_save_execution_step(status=ExecutionStatus.COMPLETED, progress=100.0)
```

#### 新增端点

1. **获取指定消息的执行步骤**
   ```
   GET /api/sessions/{session_id}/messages/{message_id}/execution-steps
   ```
   返回：`List[AgentExecutionStep]`

2. **获取最新消息的执行步骤**（推荐用于轮询）
   ```
   GET /api/sessions/{session_id}/messages/latest/execution-steps
   ```
   自动查找最新的助手消息并返回其执行步骤。

### 3. 前端集成层

#### 轮询方案（简单实现）

```javascript
class ExecutionProgressTracker {
  constructor(sessionId, token) {
    this.sessionId = sessionId;
    this.token = token;
  }

  async startPolling(callback, intervalMs = 1000) {
    const poll = async () => {
      const response = await fetch(
        `/api/sessions/${this.sessionId}/messages/latest/execution-steps`,
        { headers: { 'Authorization': `Bearer ${this.token}` } }
      );
      const steps = await response.json();
      callback(steps);

      // 检查是否完成
      const lastStep = steps[steps.length - 1];
      if (lastStep?.status === 'completed' || lastStep?.status === 'failed') {
        return; // 停止轮询
      }

      setTimeout(poll, intervalMs);
    };

    poll();
  }
}
```

#### UI 显示示例

```html
<!-- 进度条 -->
<div class="progress-bar" style="width: 50%">50%</div>

<!-- 状态显示 -->
<div>🤔 AI 正在思考...</div>

<!-- 步骤列表 -->
<div class="steps-list">
  <div class="step">
    <h4>💭 思考内容（第1轮）</h4>
    <p>用户想要创建一个待办事项列表...</p>
  </div>
  <div class="step">
    <h4>✅ 工具: write</h4>
    <pre>{"filename": "index.html", ...}</pre>
  </div>
</div>
```

## 工作流程

### 完整的交互流程

```
1. 用户发送消息
   ↓
2. 后端创建空的 Assistant Message (message_id=123)
   ↓
3. 后端开始 AI Agent Loop
   ↓
4. 每个关键步骤保存到数据库
   - THINKING (progress=10%)
   - TOOL_CALLING (tool=write, progress=20%)
   - TOOL_EXECUTING (tool=write, progress=25%)
   - TOOL_COMPLETED (tool=write, result="...", progress=30%)
   - THINKING (第2轮, progress=35%)
   - COMPLETED (progress=100%)
   ↓
5. 前端轮询 /api/sessions/{id}/messages/latest/execution-steps
   ↓
6. 前端收到步骤更新，显示进度
   - 更新进度条
   - 显示当前状态
   - 渲染步骤列表
   ↓
7. 后端完成，更新 Assistant Message 的最终内容
   ↓
8. 前端检测到 completed 状态，停止轮询
```

## 执行状态说明

| 状态 | 说明 | 进度范围 |
|------|------|---------|
| `thinking` | AI 正在思考 | 10%-85% |
| `tool_calling` | AI 决定调用工具 | 20%-90% |
| `tool_executing` | 工具正在执行 | 25%-92% |
| `tool_completed` | 工具执行完成 | 30%-95% |
| `completed` | 全部完成 | 100% |
| `failed` | 执行失败 | N/A |

## 文件清单

### 后端文件

- `backend/app/models/agent_execution.py` - 执行步骤数据模型
- `backend/app/models/__init__.py` - 模型导出（已更新）
- `backend/app/api/messages.py` - API 端点（已修改，添加进度保存和查询）
- `backend/app/main.py` - 应用入口（已更新，导入新模型）
- `backend/tests/test_execution_progress.py` - 测试脚本

### 文档文件

- `backend/docs/execution_progress_integration.md` - 前端集成指南
- `backend/docs/EXECUTION_PROGRESS_FEATURE.md` - 本文档

## 使用示例

### 1. 启动服务器

```bash
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 发送消息

```bash
curl -X POST "http://localhost:8000/api/sessions/{session_id}/messages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "帮我创建一个待办事项列表"}'
```

### 3. 轮询执行进度

```bash
curl "http://localhost:8000/api/sessions/{session_id}/messages/latest/execution-steps" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**响应示例**：
```json
[
  {
    "id": 1,
    "session_id": "abc123",
    "message_id": 456,
    "iteration": 1,
    "status": "thinking",
    "reasoning_content": "用户想要创建一个待办事项列表...",
    "progress": 10.0,
    "created_at": "2025-01-14T10:30:00Z"
  },
  {
    "id": 2,
    "session_id": "abc123",
    "message_id": 456,
    "iteration": 1,
    "status": "tool_calling",
    "tool_name": "write",
    "tool_arguments": {"filename": "index.html", "content": "..."},
    "progress": 20.0,
    "created_at": "2025-01-14T10:30:05Z"
  },
  {
    "id": 3,
    "status": "completed",
    "progress": 100.0,
    "created_at": "2025-01-14T10:30:10Z"
  }
]
```

## 测试

运行测试脚本：

```bash
cd backend
uv run python tests/test_execution_progress.py
```

测试包括：
- 创建测试用户、会话、消息
- 创建多个执行步骤
- 查询和验证数据
- 输出 JSON 格式示例

## 注意事项

### 性能优化

1. **轮询频率**：建议 1-2 秒轮询一次，避免过于频繁
2. **停止轮询**：检测到 `completed` 或 `failed` 后必须停止
3. **数据清理**：定期清理旧的执行步骤（可选）

### 数据库迁移

现有数据库需要添加 `tool_calls` 字段：

```sql
ALTER TABLE messages ADD COLUMN tool_calls TEXT;
```

新表会在服务器启动时自动创建。

### 安全性

- 所有端点都需要 JWT 认证
- 执行步骤包含敏感信息（思考内容、文件内容），需要确保访问控制

## 扩展功能

### 未来可能的改进

1. **SSE 实时推送**：替代轮询，提供更实时的更新
2. **用户交互**：允许用户确认或拒绝工具调用
3. **错误恢复**：支持重试失败的工具调用
4. **进度暂停**：支持暂停和恢复执行
5. **数据清理**：自动清理超过 N 天的执行步骤

## 相关文档

- [前端集成指南](./execution_progress_integration.md)
- [DeepSeek API 文档](https://api-docs.deepseek.com/zh-cn/)
- [项目主文档](../CLAUDE.md)

## 总结

这个功能为 AI Agent Sandbox 添加了完整的执行进度追踪能力，实现了：

✅ **持久化存储**：所有步骤保存到数据库
✅ **实时更新**：前端可通过轮询获取最新进度
✅ **详细追踪**：记录思考、工具调用、执行结果等详细信息
✅ **用户友好**：提供清晰的进度条和状态显示
✅ **易于集成**：提供简单的前端集成示例

该功能已通过测试，可以投入使用。
