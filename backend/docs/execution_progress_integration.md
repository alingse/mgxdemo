# AI 执行进度追踪 - 前端集成指南

## 概述

本系统支持实时追踪 AI 在执行任务时的进度，包括思考状态、工具调用、工具执行等步骤。所有步骤都会持久化到数据库，前端可以通过轮询 API 获取最新进度。

## 数据结构

### 执行步骤（AgentExecutionStep）

```typescript
interface ExecutionStep {
  id: number;
  session_id: string;
  message_id: number;
  iteration: number;           // 第几轮循环
  status: string;              // 执行状态（见下方）
  reasoning_content?: string;  // AI 思考内容
  tool_name?: string;          // 工具名称
  tool_arguments?: object;     // 工具参数
  tool_result?: string;        // 工具执行结果
  tool_error?: string;         // 工具执行错误
  progress: number;            // 进度百分比（0-100）
  created_at: string;          // ISO 8601 时间戳
  updated_at: string;          // ISO 8601 时间戳
}
```

### 执行状态（ExecutionStatus）

```typescript
type ExecutionStatus =
  | "thinking"        // AI 正在思考
  | "tool_calling"    // AI 决定调用工具
  | "tool_executing"  // 工具正在执行
  | "tool_completed"  // 工具执行完成
  | "finalizing"      // 生成最终答案
  | "completed"       // 全部完成
  | "failed";         // 执行失败
```

## API 端点

### 1. 获取指定消息的执行步骤

```
GET /api/sessions/{session_id}/messages/{message_id}/execution-steps
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
    "session_id": "abc123",
    "message_id": 456,
    "iteration": 1,
    "status": "tool_completed",
    "tool_name": "write",
    "tool_result": "文件写入成功",
    "progress": 30.0,
    "created_at": "2025-01-14T10:30:06Z"
  },
  {
    "id": 4,
    "session_id": "abc123",
    "message_id": 456,
    "iteration": 2,
    "status": "completed",
    "progress": 100.0,
    "created_at": "2025-01-14T10:30:10Z"
  }
]
```

### 2. 获取最新消息的执行步骤（推荐）

```
GET /api/sessions/{session_id}/messages/latest/execution-steps
```

这个端点自动查找最新的助手消息并返回其执行步骤，**推荐用于轮询**。

## 前端集成示例

### 方案 1：轮询（简单实现）

```javascript
class ExecutionProgressTracker {
  constructor(sessionId, token) {
    this.sessionId = sessionId;
    this.token = token;
    this.pollingInterval = null;
    this.isPolling = false;
  }

  // 开始轮询
  startPolling(callback, intervalMs = 1000) {
    if (this.isPolling) return;

    this.isPolling = true;
    this.poll(callback, intervalMs);
  }

  // 停止轮询
  stopPolling() {
    this.isPolling = false;
    if (this.pollingInterval) {
      clearTimeout(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  // 轮询逻辑
  async poll(callback, intervalMs) {
    if (!this.isPolling) return;

    try {
      const steps = await this.fetchLatestSteps();
      callback(steps);

      // 如果最后一步是 completed 或 failed，停止轮询
      const lastStep = steps[steps.length - 1];
      if (lastStep && (lastStep.status === 'completed' || lastStep.status === 'failed')) {
        this.stopPolling();
        return;
      }

      // 继续轮询
      this.pollingInterval = setTimeout(() => {
        this.poll(callback, intervalMs);
      }, intervalMs);
    } catch (error) {
      console.error('轮询执行步骤失败:', error);
      // 出错时继续轮询
      this.pollingInterval = setTimeout(() => {
        this.poll(callback, intervalMs);
      }, intervalMs);
    }
  }

  // 获取最新的执行步骤
  async fetchLatestSteps() {
    const response = await fetch(
      `/api/sessions/${this.sessionId}/messages/latest/execution-steps`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }
}
```

### 使用示例

```javascript
// 初始化
const tracker = new ExecutionProgressTracker('session-id-here', 'your-jwt-token');

// 开始轮询，每秒更新一次
tracker.startPolling((steps) => {
  console.log('执行步骤更新:', steps);
  updateUI(steps);
});

// 停止轮询
// tracker.stopPolling();

// UI 更新函数
function updateUI(steps) {
  if (steps.length === 0) return;

  const lastStep = steps[steps.length - 1];

  // 更新进度条
  updateProgressBar(lastStep.progress);

  // 更新状态显示
  updateStatusDisplay(lastStep);

  // 更新步骤列表
  updateStepsList(steps);
}

function updateProgressBar(progress) {
  const progressBar = document.getElementById('progress-bar');
  if (progressBar) {
    progressBar.style.width = `${progress}%`;
    progressBar.textContent = `${Math.round(progress)}%`;
  }
}

function updateStatusDisplay(step) {
  const statusElement = document.getElementById('status-display');
  if (!statusElement) return;

  const statusTexts = {
    'thinking': '🤔 AI 正在思考...',
    'tool_calling': '🔧 AI 正在调用工具...',
    'tool_executing': `⚙️ 正在执行: ${step.tool_name || '未知工具'}`,
    'tool_completed': `✅ ${step.tool_name || '工具'} 执行完成`,
    'completed': '🎉 任务完成！',
    'failed': '❌ 执行失败'
  };

  statusElement.textContent = statusTexts[step.status] || step.status;
}

function updateStepsList(steps) {
  const container = document.getElementById('steps-container');
  if (!container) return;

  // 清空现有内容
  container.innerHTML = '';

  // 渲染每个步骤
  steps.forEach(step => {
    const stepElement = document.createElement('div');
    stepElement.className = 'step-item';

    let content = '';
    if (step.status === 'thinking' && step.reasoning_content) {
      content = `
        <div class="step-thinking">
          <h4>💭 思考内容（第${step.iteration}轮）</h4>
          <p>${step.reasoning_content.substring(0, 200)}...</p>
        </div>
      `;
    } else if (step.tool_name) {
      const isError = step.status === 'failed';
      content = `
        <div class="step-tool ${isError ? 'error' : ''}">
          <h4>${isError ? '❌' : '✅'} 工具: ${step.tool_name}</h4>
          ${step.tool_arguments ? `<pre>${JSON.stringify(step.tool_arguments, null, 2)}</pre>` : ''}
          ${step.tool_result ? `<p class="result">${step.tool_result.substring(0, 200)}...</p>` : ''}
          ${step.tool_error ? `<p class="error">${step.tool_error}</p>` : ''}
        </div>
      `;
    }

    stepElement.innerHTML = `
      <div class="step-header">
        <span class="step-status">${step.status}</span>
        <span class="step-time">${new Date(step.created_at).toLocaleTimeString()}</span>
      </div>
      ${content}
    `;

    container.appendChild(stepElement);
  });
}
```

### HTML 模板

```html
<!-- 进度显示区域 -->
<div class="execution-progress">
  <div class="progress-container">
    <div class="progress-bar" id="progress-bar" style="width: 0%">0%</div>
  </div>

  <div class="status-display" id="status-display">
    等待开始...
  </div>

  <div class="steps-container" id="steps-container">
    <!-- 步骤列表将在这里渲染 -->
  </div>
</div>

<style>
.execution-progress {
  padding: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin: 20px 0;
}

.progress-container {
  width: 100%;
  height: 30px;
  background-color: #f0f0f0;
  border-radius: 15px;
  overflow: hidden;
  margin-bottom: 15px;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #8BC34A);
  transition: width 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
}

.status-display {
  font-size: 18px;
  padding: 10px;
  background-color: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 15px;
}

.steps-container {
  max-height: 400px;
  overflow-y: auto;
}

.step-item {
  padding: 10px;
  margin-bottom: 10px;
  border-left: 3px solid #4CAF50;
  background-color: #f9f9f9;
}

.step-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}

.step-status {
  font-weight: bold;
  text-transform: uppercase;
  color: #666;
}

.step-time {
  color: #999;
  font-size: 12px;
}

.step-tool {
  margin-top: 10px;
}

.step-tool.error {
  border-left-color: #f44336;
}

.step-tool pre {
  background-color: #f0f0f0;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

.step-tool .result {
  color: #4CAF50;
}

.step-tool .error {
  color: #f44336;
}
</style>
```

### 方案 2：React Hook 实现

```javascript
import { useState, useEffect, useCallback, useRef } from 'react';

function useExecutionProgress(sessionId, token, enabled = true) {
  const [steps, setSteps] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const pollingRef = useRef(null);

  const fetchSteps = useCallback(async () => {
    try {
      const response = await fetch(
        `/api/sessions/${sessionId}/messages/latest/execution-steps`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setSteps(data);
      setError(null);

      // 检查是否完成
      const lastStep = data[data.length - 1];
      return lastStep && (lastStep.status === 'completed' || lastStep.status === 'failed');
    } catch (err) {
      setError(err.message);
      return false;
    }
  }, [sessionId, token]);

  useEffect(() => {
    if (!enabled) return;

    setIsLoading(true);

    // 立即获取一次
    fetchSteps().then((isCompleted) => {
      setIsLoading(false);

      // 如果未完成，开始轮询
      if (!isCompleted) {
        pollingRef.current = setInterval(async () => {
          const completed = await fetchSteps();
          if (completed) {
            clearInterval(pollingRef.current);
            setIsLoading(false);
          }
        }, 1000);
      }
    });

    // 清理函数
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [enabled, fetchSteps]);

  // 手动刷新
  const refetch = useCallback(() => {
    return fetchSteps();
  }, [fetchSteps]);

  return {
    steps,
    isLoading,
    error,
    refetch,
    // 便捷属性
    isCompleted: steps[steps.length - 1]?.status === 'completed',
    isFailed: steps[steps.length - 1]?.status === 'failed',
    currentProgress: steps[steps.length - 1]?.progress || 0,
  };
}

// 使用示例
function ExecutionProgress({ sessionId, token }) {
  const { steps, isLoading, error, isCompleted, currentProgress } =
    useExecutionProgress(sessionId, token);

  return (
    <div className="execution-progress">
      <div className="progress-container">
        <div
          className="progress-bar"
          style={{ width: `${currentProgress}%` }}
        >
          {Math.round(currentProgress)}%
        </div>
      </div>

      {isLoading && <p>正在加载...</p>}
      {error && <p className="error">{error}</p>}

      <div className="steps-list">
        {steps.map((step) => (
          <StepItem key={step.id} step={step} />
        ))}
      </div>
    </div>
  );
}
```

## 工作流程

### 完整的交互流程

```
1. 用户发送消息
   ↓
2. 后端创建空的 Assistant Message（message_id=123）
   ↓
3. 后端开始 AI Agent Loop
   ↓
4. 每个步骤保存到数据库
   - THINKING (progress=10%)
   - TOOL_CALLING (progress=20%)
   - TOOL_EXECUTING (progress=25%)
   - TOOL_COMPLETED (progress=30%)
   - THINKING (第2轮, progress=35%)
   - COMPLETED (progress=100%)
   ↓
5. 前端轮询 /api/sessions/{id}/messages/latest/execution-steps
   ↓
6. 前端收到步骤更新，显示进度
   ↓
7. 后端完成，更新 Assistant Message 的最终内容
   ↓
8. 前端检测到 completed 状态，停止轮询
```

## 注意事项

1. **轮询频率**：建议 1-2 秒轮询一次，过于频繁会增加服务器负担
2. **停止轮询**：检测到 `completed` 或 `failed` 状态后必须停止轮询
3. **错误处理**：网络错误时应该继续轮询，而不是立即停止
4. **JWT Token**：确保在请求头中携带有效的认证令牌
5. **思考内容**：`reasoning_content` 可能很长，建议只显示前 200 字符

## 扩展功能

### 添加交互功能（取消/重试）

```javascript
// 取消当前执行
async function cancelExecution(sessionId, messageId) {
  // 可以在后端添加取消端点
  await fetch(`/api/sessions/${sessionId}/messages/${messageId}/cancel`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
  });
}

// 重试失败的工具
async function retryTool(sessionId, messageId, toolName) {
  await fetch(`/api/sessions/${sessionId}/messages/${messageId}/retry`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ tool_name: toolName })
  });
}
```

### SSE 实时推送（高级）

如果需要更实时的推送，可以考虑使用 Server-Sent Events (SSE)：

```javascript
const eventSource = new EventSource(
  `/api/sessions/${sessionId}/messages/${messageId}/execution-stream`,
  {
    headers: { 'Authorization': `Bearer ${token}` }
  }
);

eventSource.onmessage = (event) => {
  const step = JSON.parse(event.data);
  console.log('新步骤:', step);
  updateUI([step]);
};

eventSource.onerror = (error) => {
  console.error('SSE 错误:', error);
  eventSource.close();
};
```

这需要在后端实现 SSE 端点（后续可以添加）。
