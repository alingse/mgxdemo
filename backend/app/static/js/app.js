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

    toggleSidebar() {
        sidebarVisible = !sidebarVisible;
        elements.sessionSidebar.classList.toggle('hidden', !sidebarVisible);
    },

    showSidebar() {
        sidebarVisible = true;
        elements.sessionSidebar.classList.remove('hidden');
    },

    hideSidebar() {
        sidebarVisible = false;
        elements.sessionSidebar.classList.add('hidden');
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

    messages.forEach(message => {
        const div = document.createElement('div');
        div.className = `message message-${message.role}`;

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
            div.appendChild(reasoningDiv);
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
            div.appendChild(toolsDiv);
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

        div.appendChild(bubble);
        div.appendChild(time);
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

    try {
        await api.createMessage(currentSession.id, content);
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
            alert('会话不存在或无权访问');
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
    elements.showSessionsBtn.addEventListener('click', ui.showSidebar);
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
