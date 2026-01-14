// App state
let currentSession = null;
let sessions = [];
let currentUser = null;
let sidebarVisible = false;

// DOM elements
const sessionSidebar = document.getElementById('sessionSidebar');
const sessionsList = document.getElementById('sessionsList');
const messagesContainer = document.getElementById('messagesContainer');
const messageForm = document.getElementById('messageForm');
const messageInput = document.getElementById('messageInput');
const previewFrame = document.getElementById('previewFrame');
const userInfo = document.getElementById('userInfo');
const newSessionBtn = document.getElementById('newSessionBtn');
const logoutBtn = document.getElementById('logoutBtn');
const refreshPreviewBtn = document.getElementById('refreshPreviewBtn');
const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
const currentSessionTitle = document.getElementById('currentSessionTitle');

// Extract session_id from URL
function getSessionIdFromURL() {
    const pathParts = window.location.pathname.split('/');
    const sessionId = pathParts[pathParts.length - 1];

    // Validate if it's a valid UUID hex format (32 characters)
    if (sessionId && /^[0-9a-f]{32}$/.test(sessionId)) {
        return sessionId;
    }
    return null;
}

// Initialize app
async function initApp() {
    // Check auth
    currentUser = await checkAuth();
    if (!currentUser) {
        // Store intended URL for redirect after login
        localStorage.setItem('intended_url', window.location.pathname);
        window.location.href = '/sign-in';
        return;
    }

    // Set user info
    userInfo.textContent = currentUser.username;

    // Extract session_id from URL
    const sessionId = getSessionIdFromURL();

    if (sessionId) {
        // Load specific session from URL
        try {
            // Load all sessions first
            await loadSessions();

            // Try to get the specific session
            const session = await api.getSession(sessionId);

            // Find and select the session
            const targetSession = sessions.find(s => s.id === sessionId);
            if (targetSession) {
                await selectSession(targetSession);
            } else {
                // Session not in list (shouldn't happen)
                console.error('Session not found in list');
                window.location.href = '/';
                return;
            }
        } catch (error) {
            console.error('Failed to load session:', error);
            alert('会话不存在或无权访问');
            window.location.href = '/';
            return;
        }
    } else {
        // No session_id in URL, load all sessions
        await loadSessions();

        // Auto-create session if user has no sessions
        if (sessions.length === 0) {
            try {
                const session = await api.createSession('新会话');
                sessions.unshift(session);
                await selectSession(session);
            } catch (error) {
                console.error('Failed to auto-create session:', error);
            }
        }
    }

    // Check for pending message from home page
    const pendingMessage = localStorage.getItem('pending_message');
    if (pendingMessage) {
        localStorage.removeItem('pending_message');

        // If no session is selected, select the first one
        if (!currentSession && sessions.length > 0) {
            await selectSession(sessions[0]);
        }

        // Fill in the message input and auto-send
        if (currentSession) {
            messageInput.value = pendingMessage;
            // Auto-submit the pending message
            setTimeout(() => {
                messageForm.dispatchEvent(new Event('submit'));
            }, 500);
        }
    }

    // Setup event listeners
    setupEventListeners();
}

// Load sessions
async function loadSessions() {
    try {
        sessions = await api.listSessions();
        renderSessions();
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

// Render sessions
function renderSessions() {
    sessionsList.textContent = '';

    if (sessions.length === 0) {
        const emptyMsg = document.createElement('p');
        emptyMsg.style.cssText = 'padding: 15px; color: #999; text-align: center;';
        emptyMsg.textContent = '暂无会话';
        sessionsList.appendChild(emptyMsg);
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
        time.textContent = new Date(session.updated_at).toLocaleString('zh-CN');

        item.appendChild(title);
        item.appendChild(time);

        item.addEventListener('click', () => selectSession(session));
        sessionsList.appendChild(item);
    });
}

// Select session
async function selectSession(session) {
    currentSession = session;
    currentSessionTitle.textContent = session.title;
    renderSessions();
    await loadMessages();
    updatePreview();
    enableMessageForm();
}

// Load messages
async function loadMessages() {
    if (!currentSession) {
        const emptyState = document.createElement('p');
        emptyState.className = 'empty-state';
        emptyState.textContent = '选择或创建一个会话开始聊天';
        messagesContainer.textContent = '';
        messagesContainer.appendChild(emptyState);
        return;
    }

    try {
        const messages = await api.listMessages(currentSession.id);
        renderMessages(messages);
    } catch (error) {
        console.error('Failed to load messages:', error);
        const errorMsg = document.createElement('p');
        errorMsg.className = 'empty-state';
        errorMsg.textContent = '加载消息失败';
        messagesContainer.textContent = '';
        messagesContainer.appendChild(errorMsg);
    }
}

// Render messages
function renderMessages(messages) {
    messagesContainer.textContent = '';

    if (messages.length === 0) {
        const emptyState = document.createElement('p');
        emptyState.className = 'empty-state';
        emptyState.textContent = '开始聊天吧';
        messagesContainer.appendChild(emptyState);
        return;
    }

    messages.forEach(message => {
        const div = document.createElement('div');
        div.className = `message message-${message.role}`;

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.textContent = message.content;

        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date(message.created_at).toLocaleTimeString('zh-CN');

        div.appendChild(bubble);
        div.appendChild(time);
        messagesContainer.appendChild(div);
    });

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Create new session
async function createNewSession() {
    const title = prompt('请输入会话标题:', '新会话');
    if (!title) return;

    try {
        const session = await api.createSession(title);
        sessions.unshift(session);
        await selectSession(session);
    } catch (error) {
        alert('创建会话失败: ' + error.message);
    }
}

// Send message
async function sendMessage(e) {
    e.preventDefault();

    const content = messageInput.value.trim();
    if (!content || !currentSession) return;

    // Disable input
    messageInput.disabled = true;
    messageInput.value = '';

    try {
        const message = await api.createMessage(currentSession.id, content);
        // Reload messages to get the full conversation
        await loadMessages();
        // Refresh preview if files were updated
        setTimeout(() => refreshPreview(), 500);
    } catch (error) {
        alert('发送消息失败: ' + error.message);
    } finally {
        messageInput.disabled = false;
        messageInput.focus();
    }
}

// Update preview
function updatePreview() {
    if (!currentSession) {
        previewFrame.srcdoc = '<html><body style="display:flex;justify-content:center;align-items:center;height:100vh;margin:0;font-family:sans-serif;color:#666;"><p>选择或创建一个会话开始预览</p></body></html>';
        return;
    }

    const previewUrl = api.getPreviewUrl(currentSession.id);
    previewFrame.src = previewUrl;
}

// Refresh preview
function refreshPreview() {
    if (currentSession) {
        const previewUrl = api.getPreviewUrl(currentSession.id);
        previewFrame.src = previewUrl;
    }
}

// Enable message form
function enableMessageForm() {
    messageInput.disabled = false;
    const sendBtn = messageForm.querySelector('.send-icon-btn');
    if (sendBtn) {
        sendBtn.disabled = false;
    }
}

// Toggle sidebar
function toggleSidebar() {
    sidebarVisible = !sidebarVisible;
    if (sidebarVisible) {
        sessionSidebar.classList.remove('hidden');
    } else {
        sessionSidebar.classList.add('hidden');
    }
}

// Setup event listeners
function setupEventListeners() {
    newSessionBtn.addEventListener('click', createNewSession);
    messageForm.addEventListener('submit', sendMessage);
    logoutBtn.addEventListener('click', handleLogout);
    refreshPreviewBtn.addEventListener('click', refreshPreview);
    toggleSidebarBtn.addEventListener('click', toggleSidebar);

    // Enter key to send message
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!messageInput.disabled && messageInput.value.trim()) {
                messageForm.dispatchEvent(new Event('submit'));
            }
        }
    });
}

// Initialize on page load
initApp();
