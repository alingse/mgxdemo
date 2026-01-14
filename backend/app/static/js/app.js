// 应用状态
let currentSession = null;
let sessions = [];
let currentUser = null;
let sidebarVisible = false;

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
    hideSessionsBtn: document.getElementById('hideSessionsBtn'),
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

// UI 操作
const ui = {
    showAIStatus(status, text) {
        const statusDiv = document.getElementById('ai-status');
        const statusText = document.getElementById('status-text');
        const statusDot = statusDiv.querySelector('.status-dot');

        statusDiv.classList.remove('hidden');
        statusText.textContent = text;
        statusDot.classList.remove('thinking', 'tool-calling', 'error');

        if (status === 'thinking') {
            statusDot.classList.add('thinking');
        } else if (status === 'tool-calling') {
            statusDot.classList.add('tool-calling');
        } else if (status === 'error') {
            statusDot.classList.add('error');
        }
    },

    hideAIStatus() {
        document.getElementById('ai-status').classList.add('hidden');
    },

    /**
     * 更新进度显示
     * @param {Array} steps - 执行步骤数组
     */
    updateProgress(steps) {
        if (!steps || steps.length === 0) return;

        const latest = steps[steps.length - 1];

        // 更新进度条
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        if (progressBar && progressText) {
            const progress = Math.round(latest.progress || 0);
            progressBar.style.width = `${progress}%`;
            progressText.textContent = `${progress}%`;

            // 更新进度条颜色
            progressBar.classList.remove('thinking', 'tool-calling', 'tool-executing', 'completed', 'failed');
            if (latest.status === 'thinking') {
                progressBar.classList.add('thinking');
            } else if (latest.status === 'tool_calling' || latest.status === 'tool_executing') {
                progressBar.classList.add('tool-executing');
            } else if (latest.status === 'completed') {
                progressBar.classList.add('completed');
            } else if (latest.status === 'failed') {
                progressBar.classList.add('failed');
            }
        }

        // 更新状态文本
        const statusTextElement = document.getElementById('status-text');
        if (statusTextElement) {
            if (latest.status === 'thinking') {
                statusTextElement.textContent = 'AI 正在思考...';
            } else if (latest.status === 'tool_calling') {
                statusTextElement.textContent = `准备调用工具: ${latest.tool_name || '未知'}`;
            } else if (latest.status === 'tool_executing') {
                statusTextElement.textContent = `正在执行: ${latest.tool_name || '未知'}`;
            } else if (latest.status === 'tool_completed') {
                statusTextElement.textContent = `工具执行完成`;
            } else if (latest.status === 'completed') {
                statusTextElement.textContent = '执行完成';
            } else if (latest.status === 'failed') {
                statusTextElement.textContent = '执行失败';
            }
        }

        // 更新状态点
        const statusDot = document.querySelector('.status-dot');
        if (statusDot) {
            statusDot.classList.remove('thinking', 'tool-calling', 'error');
            if (latest.status === 'thinking') {
                statusDot.classList.add('thinking');
            } else if (latest.status === 'tool_calling' || latest.status === 'tool_executing') {
                statusDot.classList.add('tool-calling');
            } else if (latest.status === 'failed') {
                statusDot.classList.add('error');
            }
        }

        // 更新执行步骤列表
        this.updateExecutionSteps(steps);
    },

    /**
     * 更新执行步骤列表
     * @param {Array} steps - 执行步骤数组
     */
    updateExecutionSteps(steps) {
        const stepsContainer = document.getElementById('executionSteps');
        if (!stepsContainer) return;

        // 清空现有内容
        stepsContainer.innerHTML = '';

        // 渲染每个步骤
        steps.forEach((step, index) => {
            const stepDiv = document.createElement('div');
            stepDiv.className = `execution-step ${index === steps.length - 1 ? 'active' : ''}`;

            // 状态图标
            const statusIcon = this.getStatusIcon(step.status);

            // 工具名称或状态描述
            let title = step.tool_name || this.getStatusText(step.status);

            // 对于纯思考步骤，显示思考内容预览作为副标题
            let subtitle = '';
            if (step.status === 'thinking' && step.reasoning_content && !step.tool_name) {
                const previewText = step.reasoning_content.substring(0, 100);
                subtitle = `<div class="step-subtitle">${this.escapeHtml(previewText)}${step.reasoning_content.length > 100 ? '...' : ''}</div>`;
            }

            // 时间戳
            const time = utils.formatTime(step.created_at);

            let detailsHtml = '';

            // 思考内容（对于纯思考步骤，思考内容已经在副标题中显示，这里可以省略或显示完整内容）
            if (step.reasoning_content && (step.tool_name || step.tool_arguments || step.tool_result)) {
                // 只有在有工具调用时，才将思考内容放在 details 中
                const fullContent = this.escapeHtml(step.reasoning_content);
                detailsHtml += `
                    <details class="step-details" ${step.status === 'thinking' ? 'open' : ''}>
                        <summary>💭 思考过程</summary>
                        <pre>${fullContent}</pre>
                    </details>
                `;
            } else if (step.reasoning_content && !step.tool_name) {
                // 纯思考步骤：显示完整的思考内容（不需要折叠）
                detailsHtml += `
                    <div class="step-thinking-content">
                        <pre>${this.escapeHtml(step.reasoning_content)}</pre>
                    </div>
                `;
            }

            // 工具参数
            if (step.tool_arguments) {
                const argsStr = JSON.stringify(step.tool_arguments, null, 2);
                const previewArgs = argsStr.substring(0, 200);
                detailsHtml += `
                    <details class="step-details">
                        <summary>🔧 工具参数</summary>
                        <pre>${argsStr.length > 200 ? previewArgs + '...' : this.escapeHtml(argsStr)}</pre>
                    </details>
                `;
            }

            // 工具结果
            if (step.tool_result) {
                const previewResult = this.escapeHtml(step.tool_result.substring(0, 200));
                detailsHtml += `
                    <details class="step-details">
                        <summary>✓ 执行结果</summary>
                        <pre>${step.tool_result.length > 200 ? previewResult + '...' : previewResult}</pre>
                    </details>
                `;
            }

            // 工具错误
            if (step.tool_error) {
                detailsHtml += `
                    <div class="step-error">
                        <strong>❌ 错误:</strong> ${this.escapeHtml(step.tool_error)}
                    </div>
                `;
            }

            stepDiv.innerHTML = `
                <div class="step-header">
                    <span class="step-icon">${statusIcon}</span>
                    <div class="step-title-wrapper">
                        <span class="step-title">${this.escapeHtml(title)}</span>
                        ${subtitle}
                    </div>
                    <span class="step-time">${time}</span>
                </div>
                ${detailsHtml}
            `;

            stepsContainer.appendChild(stepDiv);
        });

        // 自动滚动到底部
        stepsContainer.scrollTop = stepsContainer.scrollHeight;
    },

    /**
     * 获取状态图标
     */
    getStatusIcon(status) {
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
    },

    /**
     * 获取状态文本
     */
    getStatusText(status) {
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
    },

    /**
     * 切换执行步骤列表显示
     */
    toggleExecutionSteps() {
        const stepsContainer = document.getElementById('executionSteps');
        const toggleBtn = document.getElementById('toggleStepsBtn');
        const arrow = toggleBtn?.querySelector('.arrow');

        if (stepsContainer) {
            stepsContainer.classList.toggle('hidden');
            if (arrow) {
                arrow.textContent = stepsContainer.classList.contains('hidden') ? '▼' : '▲';
            }
        }
    },

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
        // 更新按钮图标方向
        const toggleBtn = elements.hideSessionsBtn;
        if (toggleBtn) {
            const svg = toggleBtn.querySelector('svg');
            if (sidebarVisible) {
                // 展开状态：显示收起图标（向左箭头）
                svg.innerHTML = '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="15" y1="3" x2="15" y2="21"></line>';
            } else {
                // 收起状态：显示展开图标（向右箭头）
                svg.innerHTML = '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line>';
            }
        }
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

function renderMessages(messages) {
    elements.messagesContainer.textContent = '';

    if (messages.length === 0) {
        ui.showEmptyMessage('开始聊天吧');
        return;
    }

    // 过滤掉 TOOL 消息（工具响应不需要在聊天界面显示）
    const visibleMessages = messages.filter(m => m.role !== 'tool');

    visibleMessages.forEach(message => {
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

        // 显示思考内容
        if (message.reasoning_content) {
            const reasoningDiv = document.createElement('div');
            reasoningDiv.className = 'message-reasoning';
            reasoningDiv.innerHTML = `
                <details>
                    <summary>🤔 思考过程</summary>
                    <pre>${utils.escapeHtml(message.reasoning_content)}</pre>
                </details>
            `;
            contentDiv.appendChild(reasoningDiv);
        }

        // 显示工具调用
        if (message.tool_calls && message.tool_calls.length > 0) {
            const toolsDiv = document.createElement('div');
            toolsDiv.className = 'message-tools';
            const toolsHtml = `
                <details><summary>🔧 工具调用</summary><ul>
                ${message.tool_calls.map(tool => `
                    <li>
                        <strong>${utils.escapeHtml(tool.name)}</strong>
                        <pre>${utils.escapeHtml(JSON.stringify(tool.arguments, null, 2))}</pre>
                    </li>
                `).join('')}
                </ul></details>
            `;
            toolsDiv.innerHTML = toolsHtml;
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
    });

    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

async function sendMessage(e) {
    e.preventDefault();

    const content = elements.messageInput.value.trim();
    if (!content || !currentSession) return;

    elements.messageInput.disabled = true;
    elements.messageInput.value = '';
    ui.showAIStatus('thinking', 'AI 正在思考...');

    // 重置进度条
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    if (progressBar) progressBar.style.width = '0%';
    if (progressText) progressText.textContent = '0%';

    try {
        // 创建消息
        await api.createMessage(currentSession.id, content);

        // 启动进度追踪
        const tracker = new ProgressTracker(
            currentSession.id,
            (steps) => ui.updateProgress(steps),  // onUpdate
            (success, data) => {                  // onComplete
                if (!success) {
                    console.warn('Progress tracking failed:', data);
                }
            }
        );

        tracker.start();

        // 等待完成（但设置超时保护）
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

        // 加载消息列表
        await loadMessages();
        setTimeout(() => ui.refreshPreview(), 500);
        ui.hideAIStatus();
    } catch (error) {
        ui.showAIStatus('error', '消息发送失败，请重试');
        console.error('发送消息失败:', error);
    } finally {
        elements.messageInput.disabled = false;
        elements.messageInput.focus();
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
    elements.hideSessionsBtn.addEventListener('click', ui.toggleSidebar);
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
