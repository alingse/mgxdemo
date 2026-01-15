// 应用状态
let currentSession = null;
let sessions = [];
let currentUser = null;
let sidebarVisible = false;
let currentStreamingMessage = null; // 当前正在生成的消息容器
let isReadOnlyMode = false;
let isSessionOwner = true;

// 应用常量
const CONSTANTS = {
    // 时间相关
    TOAST_DURATION: 3000,
    PENDING_MESSAGE_DELAY: 500,
    SSE_MAX_RETRIES: 5,

    // UI 显示相关
    STEP_RESULT_MAX_LENGTH: 500,
    SESSION_TITLE_MAX_LENGTH: 30,

    // 状态文本
    STATUS_TEXT: {
        'thinking': '思考中',
        'tool_calling': '工具调用',
        'tool_executing': '执行中',
        'tool_completed': '已完成',
        'finalizing': '生成最终答案',
        'completed': '完成',
        'failed': '失败'
    },

    // 状态图标
    STATUS_ICONS: {
        'thinking': '🤔',
        'tool_calling': '🔧',
        'tool_executing': '⚙️',
        'tool_completed': '✅',
        'finalizing': '📝',
        'completed': '✨',
        'failed': '❌'
    },

    // Todo 状态图标
    TODO_ICONS: {
        'pending': '⏳',
        'in_progress': '🔄',
        'completed': '✅'
    }
};

// DOM 元素引用
const elements = {
    sessionSidebar: document.getElementById('sessionSidebar'),
    sessionsList: document.getElementById('sessionsList'),
    messagesContainer: document.getElementById('messagesContainer'),
    messageForm: document.getElementById('messageForm'),
    messageInput: document.getElementById('messageInput'),
    previewFrame: document.getElementById('previewFrame'),
    userInfo: document.getElementById('userInfo'),
    newSessionBtn: document.getElementById('newSessionBtn'),
    logoutBtn: document.getElementById('logoutBtn'),
    refreshPreviewBtn: document.getElementById('refreshPreviewBtn'),
    mobileMenuBtn: document.getElementById('mobileMenuBtn'),
    showSessionsBtn: document.getElementById('showSessionsBtn'),
    newSessionInlineBtn: document.getElementById('newSessionInlineBtn'),
    currentSessionTitle: document.getElementById('currentSessionTitle'),
    shareBtn: document.getElementById('shareBtn'),
    experienceBtn: document.getElementById('experienceBtn'),
    setPublicBtn: document.getElementById('setPublicBtn'),
    readOnlyBanner: document.getElementById('readOnlyBanner')
};

// 工具函数
const utils = {
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    renderMarkdown(text) {
        if (!text) return '';
        return text
            .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    },

    getSessionIdFromURL() {
        const pathParts = window.location.pathname.split('/');
        const sessionId = pathParts[pathParts.length - 1];
        return sessionId && /^[0-9a-f]{32}$/.test(sessionId) ? sessionId : null;
    },

    generateSessionTitle() {
        const now = new Date();
        const timestamp = now.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
        return `会话 ${timestamp}`;
    },

    /**
     * 解析后端返回的日期字符串。
     * 后端返回的是 UTC 时间但没有时区后缀（如 "2025-01-15T07:01:00"），
     * JavaScript 会将其当作本地时间。需要手动解析为 UTC 时间。
     */
    _parseUTCDate(dateInput) {
        // 如果传入的是 Date 对象，直接返回
        if (dateInput instanceof Date) {
            return dateInput;
        }
        // 转换为字符串处理
        const dateStr = String(dateInput);
        const date = new Date(dateStr);
        // 如果字符串不包含时区信息（Z 或 ±HH:MM），说明是 UTC 时间
        if (!dateStr.includes('Z') && !dateStr.includes('+') && !dateStr.includes('T')) {
            return date; // 简单格式，直接返回
        }
        // 检查 ISO 格式是否有时区后缀
        const hasTimezone = /[+-]\d{2}:\d{2}$|Z$/.test(dateStr);
        if (!hasTimezone && dateStr.includes('T')) {
            // 没有时区后缀的 ISO 格式，当作 UTC 处理
            // 重新解析，添加 Z 后缀
            return new Date(dateStr + 'Z');
        }
        return date;
    },

    formatDate(dateStr, locale = 'zh-CN') {
        return this._parseUTCDate(dateStr).toLocaleString(locale);
    },

    formatTime(dateStr) {
        return this._parseUTCDate(dateStr).toLocaleTimeString('zh-CN');
    }
};

// ============================================
// 执行步骤渲染函数
// ============================================

/**
 * 创建单个执行步骤的 DOM 元素
 */
function _createExecutionStepElement(step) {
    const stepDiv = document.createElement('div');
    stepDiv.className = `execution-step ${step.status === 'thinking' || step.status === 'tool_calling' || step.status === 'tool_executing' ? 'active' : ''}`;

    const statusIcon = _getStatusIcon(step.status);
    let title = step.tool_name || _getStatusText(step.status);
    const time = utils.formatTime(step.created_at);

    let detailsHtml = '';

    // 思考内容
    if (step.reasoning_content) {
        if (step.tool_name || step.tool_arguments || step.tool_result) {
            // 有工具调用时，思考内容放在 details 中
            detailsHtml += `
                <details class="step-details" ${step.status === 'thinking' ? 'open' : ''}>
                    <summary>💭 思考过程</summary>
                    <pre>${utils.escapeHtml(step.reasoning_content)}</pre>
                </details>
            `;
        } else {
            // 纯思考步骤：完整显示
            detailsHtml += `
                <div class="step-thinking-content">
                    <pre>${utils.escapeHtml(step.reasoning_content)}</pre>
                </div>
            `;
        }
    }

    // 工具参数
    if (step.tool_arguments) {
        const args = typeof step.tool_arguments === 'string'
            ? JSON.parse(step.tool_arguments)
            : step.tool_arguments;
        detailsHtml += `
            <details class="step-details" open>
                <summary>🔧 工具参数</summary>
                <pre>${utils.escapeHtml(JSON.stringify(args, null, 2))}</pre>
            </details>
        `;
    }

    // 工具结果
    if (step.tool_result) {
        const truncated = step.tool_result.length > CONSTANTS.STEP_RESULT_MAX_LENGTH
            ? step.tool_result.substring(0, CONSTANTS.STEP_RESULT_MAX_LENGTH) + '...'
            : step.tool_result;
        detailsHtml += `
            <details class="step-details" open>
                <summary>✓ 执行结果</summary>
                <pre>${utils.escapeHtml(truncated)}</pre>
            </details>
        `;
    }

    // 工具错误
    if (step.tool_error) {
        detailsHtml += `
            <div class="step-error">
                <strong>❌ 错误:</strong> ${utils.escapeHtml(step.tool_error)}
            </div>
        `;
    }

    stepDiv.innerHTML = `
        <div class="step-header">
            <span class="step-icon">${statusIcon}</span>
            <div class="step-title-wrapper">
                <span class="step-title">${utils.escapeHtml(title)}</span>
            </div>
            <span class="step-time">${time}</span>
        </div>
        ${detailsHtml}
    `;

    return stepDiv;
}

/**
 * 合并执行步骤（前端显示优化）
 * @param {Array} steps - 原始步骤列表
 * @returns {Array} - 合并后的步骤列表
 */
function _mergeExecutionSteps(steps) {
    if (!steps || steps.length === 0) return [];

    // 按 iteration 分组
    const groups = new Map();

    for (const step of steps) {
        const iteration = step.iteration;

        if (!groups.has(iteration)) {
            groups.set(iteration, []);
        }
        groups.get(iteration).push(step);
    }

    // 合并每个组
    const mergedSteps = [];

    for (const [iteration, groupSteps] of groups) {
        // 1. 合并 thinking 步骤（取最后一个有内容的）
        const thinkingSteps = groupSteps.filter(s => s.status === 'thinking');
        if (thinkingSteps.length > 0) {
            // 取最后一个有内容的 thinking
            const lastThinking = thinkingSteps[thinkingSteps.length - 1];
            mergedSteps.push({
                ...lastThinking,
                _merged: true,  // 标记为合并后的步骤
                _originalCount: thinkingSteps.length
            });
        }

        // 2. 合并 tool 步骤（按 tool_call_id 分组）
        const toolSteps = groupSteps.filter(s =>
            ['tool_calling', 'tool_executing', 'tool_completed'].includes(s.status)
        );

        // 按 tool_call_id 分组
        const toolGroups = new Map();
        for (const step of toolSteps) {
            const key = step.tool_call_id || step.tool_name;
            if (!toolGroups.has(key)) {
                toolGroups.set(key, []);
            }
            toolGroups.get(key).push(step);
        }

        // 合并每个工具的步骤
        for (const [key, toolGroupSteps] of toolGroups) {
            // 按状态优先级：completed > executing > calling
            const priority = {
                'tool_completed': 3,
                'tool_executing': 2,
                'tool_calling': 1
            };

            toolGroupSteps.sort((a, b) => priority[b.status] - priority[a.status]);

            // 取优先级最高的作为主步骤
            const mainStep = toolGroupSteps[0];

            // 合并所有信息
            const mergedToolStep = {
                ...mainStep,
                _merged: true,
                _originalCount: toolGroupSteps.length,
                // 合并工具调用信息
                tool_name: mainStep.tool_name,
                tool_arguments: mainStep.tool_arguments,
                tool_result: toolGroupSteps.find(s => s.tool_result)?.tool_result || null,
                tool_error: toolGroupSteps.find(s => s.tool_error)?.tool_error || null
            };

            mergedSteps.push(mergedToolStep);
        }

        // 3. 不显示 completed 步骤（因为最后一步已经显示完成状态）
    }

    return mergedSteps;
}

/**
 * 渲染消息的执行步骤
 * @param {HTMLElement} container - 消息内容容器
 * @param {Array} steps - 执行步骤数组
 * @param {boolean} isStreaming - 是否为流式更新（追加模式）
 */
function _renderExecutionSteps(container, steps, isStreaming = false) {
    if (!steps || steps.length === 0) return;

    let stepsContainer = container.querySelector('.message-execution-steps');

    if (!stepsContainer) {
        stepsContainer = document.createElement('div');
        stepsContainer.className = 'message-execution-steps';
        container.insertBefore(stepsContainer, container.firstChild);
    }

    if (isStreaming) {
        // 流式更新：只添加新步骤
        const existingCount = stepsContainer.querySelectorAll('.execution-step').length;
        const newSteps = steps.slice(existingCount);

        newSteps.forEach(step => {
            const stepDiv = _createExecutionStepElement(step);
            stepsContainer.appendChild(stepDiv);
        });

        // 自动滚动到底部
        stepsContainer.scrollTop = stepsContainer.scrollHeight;
    } else {
        // 完全重新渲染
        stepsContainer.innerHTML = '';
        steps.forEach(step => {
            const stepDiv = _createExecutionStepElement(step);
            stepsContainer.appendChild(stepDiv);
        });
    }
}

/**
 * 获取状态图标
 */
function _getStatusIcon(status) {
    return CONSTANTS.STATUS_ICONS[status] || '•';
}

/**
 * 获取状态文本
 */
function _getStatusText(status) {
    return CONSTANTS.STATUS_TEXT[status] || status;
}

/**
 * 创建工具错误元素
 * @param {string} message - 错误消息
 * @returns {HTMLElement} - 错误元素
 */
function _createToolErrorElement(message) {
    const div = document.createElement('div');
    div.className = 'step-error';
    div.innerHTML = `<strong>❌ 错误:</strong> ${utils.escapeHtml(message)}`;
    return div;
}

// UI 操作
const ui = {
    toggleSidebar() {
        sidebarVisible = !sidebarVisible;
        elements.sessionSidebar.classList.toggle('open', sidebarVisible);
        this._updateSidebarOverlay();
    },

    showSidebar() {
        sidebarVisible = true;
        elements.sessionSidebar.classList.add('open');
        this._updateSidebarOverlay();
    },

    hideSidebar() {
        sidebarVisible = false;
        elements.sessionSidebar.classList.remove('open');
        this._updateSidebarOverlay();
    },

    _updateSidebarOverlay() {
        // 已禁用遮罩层功能 - 不再创建遮罩层
        const overlay = document.querySelector('.sidebar-overlay');
        if (overlay) {
            overlay.remove();
        }
    },

    updatePreview() {
        if (!currentSession) {
            elements.previewFrame.srcdoc = `
                <html><body style="display:flex;justify-content:center;align-items:center;
                height:100vh;margin:0;font-family:sans-serif;color:#666;">
                <p>选择或创建一个会话开始预览</p></body></html>
            `;
            return;
        }
        elements.previewFrame.src = api.getPreviewUrl(currentSession.id);
    },

    refreshPreview() {
        if (currentSession) {
            // 添加时间戳参数强制刷新，避免浏览器缓存
            const timestamp = Date.now();
            const previewUrl = api.getPreviewUrl(currentSession.id);
            // 使用 URL 对象正确处理查询参数
            const url = new URL(previewUrl, window.location.origin);
            url.searchParams.set('_t', timestamp);
            elements.previewFrame.src = url.toString();
        }
    },

    enableMessageForm() {
        elements.messageInput.disabled = false;
        const sendBtn = elements.messageForm.querySelector('.send-icon-btn');
        if (sendBtn) sendBtn.disabled = false;
    },

    showEmptyMessage(text) {
        const emptyState = document.createElement('p');
        emptyState.className = 'empty-state';
        emptyState.textContent = text;
        elements.messagesContainer.textContent = '';
        elements.messagesContainer.appendChild(emptyState);
    },

    showSystemMessage(text) {
        const div = document.createElement('div');
        div.className = 'message message-system';
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.textContent = text;
        div.appendChild(bubble);
        elements.messagesContainer.appendChild(div);
    },

    setReadOnlyMode(enabled) {
        isReadOnlyMode = enabled;
        document.body.classList.toggle('read-only-mode', enabled);

        if (enabled) {
            elements.readOnlyBanner.style.display = 'flex';
            elements.messageInput.disabled = true;
            elements.messageInput.placeholder = '只读模式，无法发送消息';
        } else {
            elements.readOnlyBanner.style.display = 'none';
            elements.messageInput.disabled = false;
            elements.messageInput.placeholder = '描述你的需求或修改建议...';
        }
        // 按钮显示由 selectSession 统一控制
    },

    async loadTodos() {
        if (!currentSession) return;
        try {
            const data = await api.getTodos(currentSession.id);
            ui.renderTodos(data);
        } catch (error) {
            console.error('Failed to load todos:', error);
        }
    },

    renderTodos(data) {
        const panel = document.getElementById('todosPanel');
        if (!panel) return;

        const list = panel.querySelector('.todos-list');
        const count = panel.querySelector('.todos-count');

        if (!data || !data.todos || data.todos.length === 0) {
            panel.style.display = 'none';
            return;
        }

        panel.style.display = 'block';
        count.textContent = `${data.completed}/${data.total}`;

        list.innerHTML = data.todos.map(todo => `
            <div class="todo-item todo-${todo.status}">
                <span class="todo-icon">${_getTodoIcon(todo.status)}</span>
                <span class="todo-text">${utils.escapeHtml(todo.content)}</span>
            </div>
        `).join('');
    },

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), CONSTANTS.TOAST_DURATION);
    }
};

// 会话管理
async function loadSessions() {
    try {
        sessions = await api.listSessions();
        renderSessions();
    } catch (error) {
        console.error('加载会话失败:', error);
    }
}

function renderSessions() {
    elements.sessionsList.textContent = '';

    if (sessions.length === 0) {
        const emptyMsg = document.createElement('p');
        emptyMsg.style.cssText = 'padding: 15px; color: #999; text-align: center;';
        emptyMsg.textContent = '暂无会话';
        elements.sessionsList.appendChild(emptyMsg);
        return;
    }

    sessions.forEach(session => {
        const item = document.createElement('div');
        item.className = 'session-item';
        if (currentSession && currentSession.id === session.id) {
            item.classList.add('active');
        }

        const title = document.createElement('div');
        title.className = 'session-item-title';
        title.textContent = session.title;

        const time = document.createElement('div');
        time.className = 'session-item-time';
        time.textContent = utils.formatDate(session.updated_at);

        item.appendChild(title);
        item.appendChild(time);
        item.addEventListener('click', () => selectSession(session));
        elements.sessionsList.appendChild(item);
    });
}

async function selectSession(session) {
    currentSession = session;
    elements.currentSessionTitle.textContent = session.title;

    // 获取完整会话详情以检查 is_public 和所有权
    try {
        const sessionDetail = await api.getSession(session.id);
        isSessionOwner = sessionDetail.is_owner;

        if (!isSessionOwner) {
            if (sessionDetail.is_public) {
                ui.setReadOnlyMode(true);
            } else {
                alert('您没有权限访问此会话');
                window.location.href = '/';
                return;
            }
        } else {
            ui.setReadOnlyMode(false);
        }

        // 按钮显示控制
        elements.experienceBtn.style.display = 'inline-flex';
        elements.shareBtn.style.display = 'inline-flex';
        elements.setPublicBtn.style.display = isSessionOwner && !sessionDetail.is_public ? 'inline-flex' : 'none';
        elements.refreshPreviewBtn.style.display = 'inline-flex';
    } catch (error) {
        console.error('Failed to fetch session details:', error);
    }

    renderSessions();
    await loadMessages();
    await ui.loadTodos();
    ui.updatePreview();
    if (!isReadOnlyMode) {
        ui.enableMessageForm();
    }

    // 选择会话后自动收起侧边栏（所有屏幕尺寸）
    if (sidebarVisible) {
        ui.toggleSidebar();
    }
}

async function createNewSession() {
    const title = utils.generateSessionTitle();

    try {
        const session = await api.createSession(title);
        sessions.unshift(session);
        await selectSession(session);

        if (sidebarVisible) {
            ui.toggleSidebar();
        }
    } catch (error) {
        console.error('创建会话失败:', error);
        elements.messagesContainer.textContent = '';
        ui.showSystemMessage(`创建会话失败: ${error.message}`);
    }
}

// 消息管理
async function loadMessages() {
    if (!currentSession) {
        ui.showEmptyMessage('选择或创建一个会话开始聊天');
        return;
    }

    try {
        const messages = await api.listMessages(currentSession.id);
        renderMessages(messages);
    } catch (error) {
        console.error('加载消息失败:', error);
        ui.showEmptyMessage('加载消息失败');
    }
}

async function renderMessages(messages) {
    elements.messagesContainer.textContent = '';

    if (messages.length === 0) {
        ui.showEmptyMessage('开始聊天吧');
        return;
    }

    // 过滤掉 TOOL 消息（工具响应不需要在聊天界面显示）
    const visibleMessages = messages.filter(m => m.role !== 'tool');

    // 改为 for...of 循环以支持 await
    for (const message of visibleMessages) {
        const div = document.createElement('div');
        div.className = `message message-${message.role}`;

        // 添加头像
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';

        if (message.role === 'assistant') {
            avatarDiv.innerHTML = `
                <img src="/static/img/ai-avatar.svg" alt="AI">
            `;
        } else if (message.role === 'user') {
            avatarDiv.innerHTML = `
                <img src="/static/img/user-avatar.svg" alt="User">
            `;
        }

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        // === 加载并显示执行步骤 ===
        if (message.role === 'assistant') {
            try {
                const steps = await api.getExecutionSteps(currentSession.id, message.id);
                if (steps && steps.length > 0) {
                    // 合并步骤后再显示（避免重复）
                    const mergedSteps = _mergeExecutionSteps(steps);
                    _renderExecutionSteps(contentDiv, mergedSteps);
                }
            } catch (error) {
                console.error('Failed to load execution steps:', error);
            }
        }

        // 显示工具调用（从 message.tool_calls）
        if (message.tool_calls && message.tool_calls.length > 0) {
            const toolsDiv = document.createElement('div');
            toolsDiv.className = 'message-tools';
            toolsDiv.innerHTML = `
                <details open>
                    <summary>🔧 工具调用 (${message.tool_calls.length}个)</summary>
                    <ul>
                    ${message.tool_calls.map(tool => `
                        <li>
                            <strong>${utils.escapeHtml(tool.function?.name || tool.name)}</strong>
                            <pre>${utils.escapeHtml(JSON.stringify(
                                typeof tool.function?.arguments === 'string'
                                    ? JSON.parse(tool.function.arguments)
                                    : tool.function?.arguments || tool.arguments,
                                null, 2
                            ))}</pre>
                        </li>
                    `).join('')}
                    </ul>
                </details>
            `;
            contentDiv.appendChild(toolsDiv);
        }

        // 显示消息内容（只有在有内容时才显示）
        if (message.content && message.content.trim()) {
            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';

            if (message.role === 'assistant') {
                bubble.innerHTML = utils.renderMarkdown(message.content);
            } else {
                bubble.textContent = message.content;
            }

            contentDiv.appendChild(bubble);
        }

        // 始终显示时间戳
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = utils.formatTime(message.created_at);
        contentDiv.appendChild(time);

        div.appendChild(avatarDiv);
        div.appendChild(contentDiv);
        elements.messagesContainer.appendChild(div);
    }

    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

/**
 * 创建 SSE 事件处理器
 * @param {HTMLElement} streamContentDiv - 流式内容容器
 * @param {HTMLElement} stepsContainer - 步骤容器
 * @param {HTMLElement} aiDiv - AI 消息容器
 * @param {Map} stepMap - 步骤映射
 * @returns {Object} - 事件处理器对象
 */
function _createSSEEventHandlers(streamContentDiv, stepsContainer, aiDiv, stepMap) {
    return {
        // onSync: 处理同步事件（重连时）
        onSync: (data) => {
            console.log('[SSE] Sync event, loading history...');
            console.log('[SSE] Sync data:', data);
            if (data.is_running && data.latest_step) {
                // 从数据库加载完整历史
                api.getExecutionSteps(currentSession.id, data.message_id)
                    .then(steps => {
                        console.log('[SSE] Loaded steps from API:', steps.length, 'steps');
                        console.log('[SSE] Steps:', steps.map(s => ({ id: s.id, status: s.status, time: s.created_at, hasReasoning: !!s.reasoning_content })));

                        // 先合并步骤（避免重复显示）
                        const mergedSteps = _mergeExecutionSteps(steps);
                        console.log('[SSE] Merged steps:', mergedSteps.length);

                        // 渲染合并后的步骤
                        mergedSteps.forEach(step => {
                            // 使用与 onEvent 一致的键策略
                            let key;
                            if (step.status === 'thinking') {
                                key = `${step.iteration}-thinking`;
                            } else if (step.tool_call_id) {
                                // 工具步骤：使用 tool_call_id 作为 key（覆盖 calling/executing/completed）
                                key = step.tool_call_id;
                            } else {
                                // fallback（如果没有 tool_call_id）
                                key = `${step.iteration}-${step.tool_name}`;
                            }

                            if (!stepMap.has(key)) {
                                const stepDiv = _createExecutionStepElement(step);
                                stepsContainer.appendChild(stepDiv);
                                stepMap.set(key, stepDiv);
                            } else {
                                // 已存在，更新内容和状态
                                const existingDiv = stepMap.get(key);
                                _updateStepStatus(existingDiv, step);
                                if (step.reasoning_content) {
                                    _updateReasoningContent(existingDiv, step.reasoning_content, step);
                                }
                            }
                        });
                        // 滚动主消息容器到底部，确保最新消息可见
                        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
                    });
            }
        },

        // onEvent: 处理推送事件
        onEvent: ({ event, data }) => {
            console.log('[SSE] Event:', event, data);

            // 处理 todos 更新事件
            if (event === 'todos_update' && data.todos) {
                console.log('[SSE] Updating todos:', data);
                ui.renderTodos(data);
                return;
            }

            if (data.type === 'step') {
                const step = data.data;

                // 跳过 completed 步骤（前端不显示）
                if (step.status === 'completed') {
                    console.log('[SSE] Skipping completed step');
                    return;
                }

                // 使用与 merge 逻辑一致的键策略：
                // - thinking 步骤：使用 iteration-thinking 作为键（同一 iteration 的 thinking 只显示一个）
                // - tool 步骤：使用 tool_call_id 作为统一 key（确保同一工具的不同状态映射到同一个元素）
                let key;
                if (step.status === 'thinking') {
                    key = `${step.iteration}-thinking`;
                } else if (step.tool_call_id) {
                    // 工具步骤：使用 tool_call_id 作为 key（覆盖 calling/executing/completed）
                    key = step.tool_call_id;
                } else {
                    // fallback（如果没有 tool_call_id）
                    key = `${step.iteration}-${step.tool_name}`;
                }

                // 检查是否已存在
                let stepDiv = stepMap.get(key);

                if (!stepDiv) {
                    // 不存在，创建新步骤元素（只创建一次）
                    console.log('[SSE] Creating new step element:', key, 'hasReasoning:', !!step.reasoning_content);
                    stepDiv = _createExecutionStepElement(step);
                    stepsContainer.appendChild(stepDiv);
                    stepMap.set(key, stepDiv);
                    // 滚动主消息容器到底部，确保最新消息可见
                    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
                } else {
                    // 已存在，更新状态（图标、标题等）
                    _updateStepStatus(stepDiv, step);
                }

                // 处理 reasoning_content 更新（thinking_delta 或普通 step 事件）
                if (step.reasoning_content) {
                    console.log('[SSE] Updating reasoning content:', key, 'length:', step.reasoning_content.length);
                    _updateReasoningContent(stepDiv, step.reasoning_content, step);
                    // 滚动主消息容器到底部，确保最新消息可见
                    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
                }
            }
        },

        // onError: 处理错误
        onError: (error) => {
            console.error('[SSE] Error:', error);
            const errorDiv = document.createElement('div');
            errorDiv.className = 'execution-step error';
            errorDiv.appendChild(_createToolErrorElement(error));
            stepsContainer.appendChild(errorDiv);
        },

        // onComplete: 处理完成
        onComplete: async () => {
            console.log('[SSE] Stream completed');

            // 获取最终消息内容，如果有文本回复则添加 message-bubble
            try {
                const messages = await api.listMessages(currentSession.id);
                const lastAiMsg = messages.filter(m => m.role === 'assistant').pop();

                if (lastAiMsg && lastAiMsg.content && lastAiMsg.content.trim()) {
                    // 有文本回复，添加 message-bubble
                    const existingBubble = streamContentDiv.querySelector('.message-bubble');
                    if (!existingBubble) {
                        const bubble = document.createElement('div');
                        bubble.className = 'message-bubble';
                        bubble.innerHTML = utils.renderMarkdown(lastAiMsg.content);
                        streamContentDiv.appendChild(bubble);

                        // 添加时间戳
                        const timeDiv = document.createElement('div');
                        timeDiv.className = 'message-time';
                        timeDiv.textContent = utils.formatTime(lastAiMsg.created_at);
                        streamContentDiv.appendChild(timeDiv);
                    }
                }
            } catch (error) {
                console.error('Failed to fetch final message:', error);
            }

            // 移除 streaming 状态
            aiDiv.classList.remove('streaming');

            // 滚动到底部显示完整消息
            elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;

            await ui.loadTodos();
            ui.refreshPreview();
            elements.messageInput.disabled = false;
            elements.messageInput.focus();
        }
    };
}

async function sendMessage(e) {
    e.preventDefault();

    const content = elements.messageInput.value.trim();
    if (!content || !currentSession) return;

    elements.messageInput.disabled = true;
    elements.messageInput.value = '';

    // 1. 立即显示用户消息
    const userDiv = document.createElement('div');
    userDiv.className = 'message message-user';
    userDiv.innerHTML = `
        <div class="message-avatar">
            <img src="/static/img/user-avatar.svg" alt="User">
        </div>
        <div class="message-content">
            <div class="message-bubble">${utils.escapeHtml(content)}</div>
            <div class="message-time">${utils.formatTime(new Date())}</div>
        </div>
    `;
    elements.messagesContainer.appendChild(userDiv);

    // 滚动到底部显示用户消息
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;

    // 2. 创建AI消息容器
    const aiDiv = document.createElement('div');
    aiDiv.className = 'message message-assistant streaming';
    aiDiv.innerHTML = `
        <div class="message-avatar">
            <img src="/static/img/ai-avatar.svg" alt="AI">
        </div>
        <div class="message-content stream-content">
            <div class="message-execution-steps"></div>
        </div>
    `;
    elements.messagesContainer.appendChild(aiDiv);

    // 滚动到底部显示 AI 消息容器
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;

    const streamContentDiv = aiDiv.querySelector('.stream-content');
    const stepsContainer = aiDiv.querySelector('.message-execution-steps');

    // 3. 步骤映射（用于更新现有步骤）
    const stepMap = new Map();

    try {
        // 4. 发送消息（立即返回）
        const response = await api.createMessage(currentSession.id, content);
        console.log('[sendMessage] Message created, starting SSE...');

        // 5. 创建 SSE 事件处理器并连接
        const handlers = _createSSEEventHandlers(streamContentDiv, stepsContainer, aiDiv, stepMap);
        const sseClient = new SSEClient(currentSession.id, {
            maxRetries: CONSTANTS.SSE_MAX_RETRIES,
            ...handlers
        });

        sseClient.connect();

    } catch (error) {
        console.error('发送消息失败:', error);
        ui.showSystemMessage(`发送消息失败: ${error.message}`);
        aiDiv.remove();
        elements.messageInput.disabled = false;
    }
}

// 应用初始化
async function initApp() {
    currentUser = await checkAuth();
    if (!currentUser) {
        localStorage.setItem('intended_url', window.location.pathname);
        window.location.href = '/sign-in';
        return;
    }

    elements.userInfo.textContent = currentUser.username;
    const sessionId = utils.getSessionIdFromURL();

    if (sessionId) {
        try {
            await loadSessions();
            const targetSession = sessions.find(s => s.id === sessionId);
            if (targetSession) {
                await selectSession(targetSession);
            } else {
                console.error('会话不存在');
                window.location.href = '/';
            }
        } catch (error) {
            console.error('加载会话失败:', error);
            window.location.href = '/';
        }
    } else {
        await loadSessions();

        if (sessions.length === 0) {
            try {
                const session = await api.createSession('新会话');
                sessions.unshift(session);
                await selectSession(session);
            } catch (error) {
                console.error('自动创建会话失败:', error);
            }
        }
    }

    // 处理待发送消息
    const pendingMessage = localStorage.getItem('pending_message');
    if (pendingMessage) {
        localStorage.removeItem('pending_message');

        if (!currentSession && sessions.length > 0) {
            await selectSession(sessions[0]);
        }

        if (currentSession) {
            elements.messageInput.value = pendingMessage;
            setTimeout(() => {
                elements.messageForm.dispatchEvent(new Event('submit'));
            }, CONSTANTS.PENDING_MESSAGE_DELAY);
        }
    }

    setupEventListeners();
}

function setupEventListeners() {
    setupNavigationEventListeners();
    setupMessageEventListeners();
    setupButtonEventListeners();
    setupMobileEventListeners();
}

function setupNavigationEventListeners() {
    elements.newSessionBtn.addEventListener('click', createNewSession);
    elements.logoutBtn.addEventListener('click', handleLogout);
}

function setupMessageEventListeners() {
    elements.messageForm.addEventListener('submit', sendMessage);
    elements.messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!elements.messageInput.disabled && elements.messageInput.value.trim()) {
                elements.messageForm.dispatchEvent(new Event('submit'));
            }
        }
    });
}

function setupButtonEventListeners() {
    elements.refreshPreviewBtn.addEventListener('click', ui.refreshPreview);
    elements.mobileMenuBtn.addEventListener('click', () => ui.toggleSidebar());
    elements.showSessionsBtn.addEventListener('click', () => ui.toggleSidebar());
    elements.newSessionInlineBtn.addEventListener('click', createNewSession);

    // 体验按钮：打开新窗口
    elements.experienceBtn.addEventListener('click', () => {
        if (currentSession) {
            const appUrl = `${window.location.origin}/app/${currentSession.id}`;
            window.open(appUrl, '_blank');
        }
    });

    // 分享按钮：复制链接
    elements.shareBtn.addEventListener('click', async () => {
        if (currentSession) {
            const shareUrl = `${window.location.origin}/chat/${currentSession.id}`;
            try {
                await navigator.clipboard.writeText(shareUrl);
                ui.showToast('链接已复制到剪贴板');
            } catch (error) {
                console.error('Failed to copy:', error);
                // 降级方案：提示用户手动复制
                prompt('请复制链接：', shareUrl);
            }
        }
    });

    // 设置公开按钮
    elements.setPublicBtn.addEventListener('click', async () => {
        if (!currentSession) return;
        try {
            await api.updateSession(currentSession.id, { is_public: true });
            ui.showToast('已设置为公开分享');
            elements.setPublicBtn.style.display = 'none';
        } catch (error) {
            console.error('Failed to set public:', error);
            ui.showToast('设置失败，请重试', 'error');
        }
    });
}

function setupMobileEventListeners() {
    const mobileTabs = document.getElementById('mobileTabs');
    if (!mobileTabs) return;

    const tabs = mobileTabs.querySelectorAll('.mobile-tab');
    const mainContainer = document.querySelector('.main-container');
    const previewArea = document.querySelector('.preview-area');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const view = tab.dataset.view;

            // 切换 Tab 状态
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // 切换视图
            if (view === 'preview') {
                mainContainer.classList.add('preview-mode');
                previewArea.classList.add('active');
            } else {
                mainContainer.classList.remove('preview-mode');
                previewArea.classList.remove('active');
            }
        });
    });
}

/**
 * 更新现有执行步骤元素（用于SSE推送更新）
 */
function _updateExecutionStepElement(stepDiv, step) {
    // 更新active状态
    const isActive = ['thinking', 'tool_calling', 'tool_executing'].includes(step.status);
    stepDiv.classList.toggle('active', isActive);

    // 更新图标
    const iconEl = stepDiv.querySelector('.step-icon');
    if (iconEl) {
        iconEl.textContent = _getStatusIcon(step.status);
    }

    // 更新标题
    const titleEl = stepDiv.querySelector('.step-title');
    if (titleEl) {
        const displayName = _getStepDisplayName(step);
        titleEl.textContent = displayName;
    }

    // 更新思考内容
    if (step.reasoning_content) {
        let thinkingEl = stepDiv.querySelector('.step-thinking-content pre');
        if (!thinkingEl) {
            // 创建思考内容容器
            const existingContent = stepDiv.querySelector('.step-thinking-content');
            if (existingContent) {
                thinkingEl = existingContent.querySelector('pre');
            }

            if (!thinkingEl) {
                // 需要创建新的思考内容区域
                const detailsDiv = stepDiv.querySelector('details');
                if (detailsDiv) {
                    const summary = detailsDiv.querySelector('summary');
                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'step-thinking-content';
                    const pre = document.createElement('pre');
                    pre.textContent = step.reasoning_content;
                    contentDiv.appendChild(pre);
                    summary.after(contentDiv);
                } else {
                    // 纯思考步骤，没有工具调用
                    const stepHeader = stepDiv.querySelector('.step-header');
                    if (stepHeader) {
                        const contentDiv = document.createElement('div');
                        contentDiv.className = 'step-thinking-content';
                        const pre = document.createElement('pre');
                        pre.textContent = step.reasoning_content;
                        contentDiv.appendChild(pre);
                        stepHeader.after(contentDiv);
                    }
                }
            }
        } else {
            // 更新内容（支持分片推送）
            thinkingEl.textContent = step.reasoning_content;
        }
    }

    // 更新工具结果
    if (step.tool_result) {
        let resultDetails = stepDiv.querySelector('details[data-result]');
        if (resultDetails) {
            const pre = resultDetails.querySelector('pre');
            if (pre) {
                const truncated = step.tool_result.length > CONSTANTS.STEP_RESULT_MAX_LENGTH
                    ? step.tool_result.substring(0, CONSTANTS.STEP_RESULT_MAX_LENGTH) + '...'
                    : step.tool_result;
                pre.textContent = truncated;
            }
        }
    }

    // 更新或创建工具错误
    if (step.tool_error) {
        let errorEl = stepDiv.querySelector('.step-error');
        if (!errorEl) {
            errorEl = _createToolErrorElement(step.tool_error);
            stepDiv.appendChild(errorEl);
        } else {
            errorEl.textContent = '';
            const strong = document.createElement('strong');
            strong.textContent = '❌ 错误:';
            errorEl.appendChild(strong);
            errorEl.appendChild(document.createTextNode(' ' + step.tool_error));
        }
    }
}

/**
 * 获取步骤显示名称
 */
function _getStepDisplayName(step) {
    if (step.tool_name) {
        const baseName = step.tool_name;
        switch (step.status) {
            case 'tool_calling':
                return `准备调用 ${baseName}...`;
            case 'tool_executing':
                return `正在执行 ${baseName}...`;
            case 'tool_completed':
                return `${baseName} 完成`;
            case 'failed':
                return `${baseName} 失败`;
            default:
                return baseName;
        }
    }
    return _getStatusText(step.status);
}

/**
 * 更新或添加工具参数
 */
function _updateToolArguments(stepDiv, toolArguments) {
    let argsDetails = stepDiv.querySelector('details[data-type="tool-arguments"]');
    if (!argsDetails) {
        const stepHeader = stepDiv.querySelector('.step-header');
        argsDetails = document.createElement('details');
        argsDetails.className = 'step-details';
        argsDetails.setAttribute('data-type', 'tool-arguments');
        argsDetails.open = true;

        const summary = document.createElement('summary');
        summary.textContent = '🔧 工具参数';
        argsDetails.appendChild(summary);

        const pre = document.createElement('pre');
        argsDetails.appendChild(pre);

        if (stepHeader) {
            stepHeader.after(argsDetails);
        } else {
            stepDiv.appendChild(argsDetails);
        }
    }
    const pre = argsDetails.querySelector('pre');
    if (pre) {
        const args = typeof toolArguments === 'string'
            ? JSON.parse(toolArguments)
            : toolArguments;
        pre.textContent = JSON.stringify(args, null, 2);
    }
}

/**
 * 更新或添加工具结果
 */
function _updateToolResult(stepDiv, toolResult) {
    let resultDetails = stepDiv.querySelector('details[data-type="tool-result"]');
    if (!resultDetails) {
        const stepHeader = stepDiv.querySelector('.step-header');
        resultDetails = document.createElement('details');
        resultDetails.className = 'step-details';
        resultDetails.setAttribute('data-type', 'tool-result');
        resultDetails.open = true;

        const summary = document.createElement('summary');
        summary.textContent = '✓ 执行结果';
        resultDetails.appendChild(summary);

        const pre = document.createElement('pre');
        resultDetails.appendChild(pre);

        if (stepHeader) {
            stepHeader.after(resultDetails);
        } else {
            stepDiv.appendChild(resultDetails);
        }
    }
    const pre = resultDetails.querySelector('pre');
    if (pre) {
        const truncated = toolResult.length > CONSTANTS.STEP_RESULT_MAX_LENGTH
            ? toolResult.substring(0, CONSTANTS.STEP_RESULT_MAX_LENGTH) + '...'
            : toolResult;
        pre.textContent = truncated;
    }
}

/**
 * 更新或添加工具错误
 */
function _updateToolError(stepDiv, toolError) {
    let errorEl = stepDiv.querySelector('.step-error');
    if (!errorEl) {
        errorEl = _createToolErrorElement(toolError);
        const stepHeader = stepDiv.querySelector('.step-header');
        if (stepHeader) {
            stepHeader.after(errorEl);
        } else {
            stepDiv.appendChild(errorEl);
        }
    } else {
        errorEl.textContent = '';
        const strong = document.createElement('strong');
        strong.textContent = '❌ 错误:';
        errorEl.appendChild(strong);
        errorEl.appendChild(document.createTextNode(' ' + toolError));
    }
}

/**
 * 更新步骤状态（不创建新元素）
 * @param {HTMLElement} stepDiv - 步骤元素
 * @param {Object} step - 步骤数据
 */
function _updateStepStatus(stepDiv, step) {
    // 更新 active 状态
    const isActive = ['thinking', 'tool_calling', 'tool_executing'].includes(step.status);
    stepDiv.classList.toggle('active', isActive);

    // 更新图标
    const iconEl = stepDiv.querySelector('.step-icon');
    if (iconEl) {
        iconEl.textContent = CONSTANTS.STATUS_ICONS[step.status] || '•';
    }

    // 更新标题
    const titleEl = stepDiv.querySelector('.step-title');
    if (titleEl) {
        titleEl.textContent = _getStepDisplayName(step);
    }

    // 更新工具参数、结果、错误
    if (step.tool_arguments) {
        _updateToolArguments(stepDiv, step.tool_arguments);
    }
    if (step.tool_result) {
        _updateToolResult(stepDiv, step.tool_result);
    }
    if (step.tool_error) {
        _updateToolError(stepDiv, step.tool_error);
    }
}

/**
 * 获取 todo 状态图标
 */
function _getTodoIcon(status) {
    return CONSTANTS.TODO_ICONS[status] || '•';
}

/**
 * 更新思考内容（增量更新）
 * 只为纯思考步骤更新，工具调用步骤不更新思考内容
 * @param {HTMLElement} stepDiv - 步骤元素
 * @param {string} reasoningContent - 思考内容
 * @param {Object} step - 步骤数据
 */
function _updateReasoningContent(stepDiv, reasoningContent, step) {
    // 如果是工具调用步骤，不更新思考内容
    // 工具调用步骤的思考内容应该在创建时放在 details 中，而不是更新时追加
    if (step && (step.tool_name || step.tool_arguments || step.tool_result || step.tool_error)) {
        return;
    }

    // 查找或创建思考内容容器
    let preEl = stepDiv.querySelector('.step-thinking-content pre');

    if (!preEl) {
        const stepHeader = stepDiv.querySelector('.step-header');
        if (!stepHeader) return;

        // 创建新的思考内容区域
        const contentDiv = document.createElement('div');
        contentDiv.className = 'step-thinking-content';
        preEl = document.createElement('pre');
        preEl.textContent = reasoningContent;
        contentDiv.appendChild(preEl);
        stepHeader.after(contentDiv);
    } else {
        // 更新现有内容
        preEl.textContent = reasoningContent;
    }
}

// 启动应用
initApp();
