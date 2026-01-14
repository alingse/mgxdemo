// 应用状态
let currentSession = null;
let sessions = [];
let currentUser = null;
let sidebarVisible = false;
let currentStreamingMessage = null; // 当前正在生成的消息容器

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
    showSessionsBtn: document.getElementById('showSessionsBtn'),
    newSessionInlineBtn: document.getElementById('newSessionInlineBtn'),
    currentSessionTitle: document.getElementById('currentSessionTitle')
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

    formatDate(dateStr, locale = 'zh-CN') {
        return new Date(dateStr).toLocaleString(locale);
    },

    formatTime(dateStr) {
        return new Date(dateStr).toLocaleTimeString('zh-CN');
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
            <details class="step-details">
                <summary>🔧 工具参数</summary>
                <pre>${utils.escapeHtml(JSON.stringify(args, null, 2))}</pre>
            </details>
        `;
    }

    // 工具结果
    if (step.tool_result) {
        detailsHtml += `
            <details class="step-details">
                <summary>✓ 执行结果</summary>
                <pre>${utils.escapeHtml(step.tool_result.substring(0, 500))}${step.tool_result.length > 500 ? '...' : ''}</pre>
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
    const icons = {
        'thinking': '🤔',
        'tool_calling': '🔧',
        'tool_executing': '⚙️',
        'tool_completed': '✅',
        'finalizing': '📝',
        'completed': '✨',
        'failed': '❌'
    };
    return icons[status] || '•';
}

/**
 * 获取状态文本
 */
function _getStatusText(status) {
    const texts = {
        'thinking': '思考中',
        'tool_calling': '工具调用',
        'tool_executing': '执行中',
        'tool_completed': '已完成',
        'finalizing': '生成最终答案',
        'completed': '完成',
        'failed': '失败'
    };
    return texts[status] || status;
}

// UI 操作
const ui = {
    /**
     * HTML 转义
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    toggleSidebar() {
        sidebarVisible = !sidebarVisible;
        elements.sessionSidebar.classList.toggle('open', sidebarVisible);
    },

    showSidebar() {
        sidebarVisible = true;
        elements.sessionSidebar.classList.add('open');
    },

    hideSidebar() {
        sidebarVisible = false;
        elements.sessionSidebar.classList.remove('open');
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
            elements.previewFrame.src = api.getPreviewUrl(currentSession.id);
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
    renderSessions();
    await loadMessages();
    ui.updatePreview();
    ui.enableMessageForm();
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

        // === 新增：加载并显示执行步骤 ===
        if (message.role === 'assistant') {
            try {
                const steps = await api.getExecutionSteps(currentSession.id, message.id);
                if (steps && steps.length > 0) {
                    // 显示执行步骤
                    _renderExecutionSteps(contentDiv, steps);
                }
            } catch (error) {
                console.error('Failed to load execution steps:', error);
            }
        }

        // 显示思考内容（从 message.reasoning_content）
        if (message.reasoning_content) {
            const reasoningDiv = document.createElement('div');
            reasoningDiv.className = 'message-reasoning';
            reasoningDiv.innerHTML = `
                <details open>
                    <summary>🤔 思考过程</summary>
                    <pre>${utils.escapeHtml(message.reasoning_content)}</pre>
                </details>
            `;
            contentDiv.appendChild(reasoningDiv);
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

        // 显示消息内容
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        if (message.role === 'assistant') {
            bubble.innerHTML = utils.renderMarkdown(message.content);
        } else {
            bubble.textContent = message.content;
        }

        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = utils.formatTime(message.created_at);

        contentDiv.appendChild(bubble);
        contentDiv.appendChild(time);

        div.appendChild(avatarDiv);
        div.appendChild(contentDiv);
        elements.messagesContainer.appendChild(div);
    }

    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
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

    // 2. 创建空的 AI 消息容器（包含执行步骤区域）
    const aiDiv = document.createElement('div');
    aiDiv.className = 'message message-assistant streaming';
    aiDiv.innerHTML = `
        <div class="message-avatar">
            <img src="/static/img/ai-avatar.svg" alt="AI">
        </div>
        <div class="message-content stream-content">
            <div class="message-execution-steps">
                <div class="execution-step active">
                    <div class="step-header">
                        <span class="step-icon">🤔</span>
                        <div class="step-title-wrapper">
                            <span class="step-title">准备思考...</span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="message-bubble streaming">
                <span class="typing-cursor">▋</span>
            </div>
        </div>
    `;
    elements.messagesContainer.appendChild(aiDiv);

    // 保存引用以便后续更新
    currentStreamingMessage = aiDiv;
    const streamContentDiv = aiDiv.querySelector('.stream-content');

    try {
        // 3. 发送消息
        await api.createMessage(currentSession.id, content);

        // 4. 启动进度追踪
        const tracker = new ProgressTracker(
            currentSession.id,
            (steps) => {
                // 实时更新当前正在生成消息的执行步骤
                if (currentStreamingMessage) {
                    const contentDiv = currentStreamingMessage.querySelector('.stream-content');
                    _renderExecutionSteps(contentDiv, steps, true); // true = 流式更新模式
                }
            },
            (success, data) => {
                if (!success) {
                    console.warn('Progress tracking failed:', data);
                    if (currentStreamingMessage) {
                        // 显示错误状态
                        const stepsContainer = currentStreamingMessage.querySelector('.message-execution-steps');
                        if (stepsContainer) {
                            const errorDiv = document.createElement('div');
                            errorDiv.className = 'execution-step';
                            errorDiv.innerHTML = `
                                <div class="step-error">
                                    <strong>❌ 处理失败:</strong> ${data?.message || '未知错误'}
                                </div>
                            `;
                            stepsContainer.appendChild(errorDiv);
                        }
                    }
                }
            }
        );

        tracker.start();

        // 等待完成
        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Timeout')), 6 * 60 * 1000)
        );

        try {
            await Promise.race([tracker.waitForCompletion(), timeoutPromise]);
        } catch (timeoutError) {
            console.warn('Message processing timeout');
        } finally {
            tracker.stop();
        }

        // 5. 加载最终消息列表
        await loadMessages();
        setTimeout(() => ui.refreshPreview(), 500);
    } catch (error) {
        console.error('发送消息失败:', error);
        ui.showSystemMessage(`发送消息失败: ${error.message}`);
        aiDiv.remove();
    } finally {
        elements.messageInput.disabled = false;
        elements.messageInput.focus();
        currentStreamingMessage = null; // 清空引用
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
            }, 500);
        }
    }

    setupEventListeners();
}

function setupEventListeners() {
    elements.newSessionBtn.addEventListener('click', createNewSession);
    elements.messageForm.addEventListener('submit', sendMessage);
    elements.logoutBtn.addEventListener('click', handleLogout);
    elements.refreshPreviewBtn.addEventListener('click', ui.refreshPreview);
    elements.showSessionsBtn.addEventListener('click', ui.toggleSidebar);
    elements.newSessionInlineBtn.addEventListener('click', createNewSession);

    elements.messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!elements.messageInput.disabled && elements.messageInput.value.trim()) {
                elements.messageForm.dispatchEvent(new Event('submit'));
            }
        }
    });
}

// 启动应用
initApp();
