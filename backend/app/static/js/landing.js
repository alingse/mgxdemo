// Landing page state
let currentUser = null;
let pendingInput = '';

// DOM elements
const mainForm = document.getElementById('mainForm');
const mainInput = document.getElementById('mainInput');
const sendBtn = document.getElementById('sendBtn');
const authModal = document.getElementById('authModal');
const modalOverlay = document.getElementById('modalOverlay');
const modalClose = document.getElementById('modalClose');
const examples = document.querySelectorAll('.example-tag');
const authTabs = document.querySelectorAll('.auth-tab');

// New DOM elements for header and sidebar
const unauthActions = document.getElementById('unauthActions');
const authActions = document.getElementById('authActions');
const userInfo = document.getElementById('userInfo');
const logoutBtn = document.getElementById('logoutBtn');
const sidebarToggle = document.getElementById('sidebarToggle');
const landingSidebar = document.getElementById('landingSidebar');
const sessionsList = document.getElementById('sessionsList');
const newSessionBtn = document.getElementById('newSessionBtn');

// 静默检查认证状态，不触发 401 重定向
async function checkAuthStatus() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        return null;
    }

    // 直接调用 fetch，不使用 api.getCurrentUser()（因为 api.js 会自动重定向）
    const response = await fetch('/api/auth/me', {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    });

    if (response.status === 401) {
        return null;
    }

    if (!response.ok) {
        return null;
    }

    return response.json();
}

// 初始化 landing page
async function initLanding() {
    // 静默检查认证状态
    currentUser = await checkAuthStatus();
    updateHeaderUI();

    // 如果已登录，加载会话列表
    if (currentUser) {
        loadSessions();
    }

    // Setup event listeners
    setupEventListeners();
}

// 更新 header UI
function updateHeaderUI() {
    if (currentUser) {
        // 已登录
        unauthActions.classList.add('hidden');
        authActions.classList.remove('hidden');
        userInfo.textContent = currentUser.username;
        // 登录后显示 sidebar header（但不展开）
        landingSidebar.classList.remove('hidden');
    } else {
        // 未登录
        unauthActions.classList.remove('hidden');
        authActions.classList.add('hidden');
        landingSidebar.classList.add('hidden');
    }
}

// 加载会话列表
async function loadSessions() {
    try {
        const sessions = await api.listSessions();
        renderSessions(sessions);
    } catch (error) {
        console.error('Failed to load sessions:', error);
    }
}

// 渲染会话列表
function renderSessions(sessions) {
    sessionsList.innerHTML = '';

    if (sessions.length === 0) {
        sessionsList.innerHTML = '<p class="empty-message">暂无会话</p>';
        return;
    }

    sessions.forEach(session => {
        const item = document.createElement('div');
        item.className = 'session-item';
        item.innerHTML = `
            <div class="session-title">${escapeHtml(session.title)}</div>
            <div class="session-time">${formatTime(session.updated_at)}</div>
        `;
        item.addEventListener('click', () => {
            // 跳转到聊天工作台页面
            window.location.href = `/chat/${session.id}`;
        });
        sessionsList.appendChild(item);
    });
}

// 辅助函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 解析后端返回的日期字符串。
 * 后端返回的是 UTC 时间但没有时区后缀（如 "2025-01-15T07:01:00"），
 * JavaScript 会将其当作本地时间。需要手动解析为 UTC 时间。
 */
function parseUTCDate(dateStr) {
    const date = new Date(dateStr);
    // 检查 ISO 格式是否有时区后缀
    const hasTimezone = /[+-]\d{2}:\d{2}$|Z$/.test(dateStr);
    if (!hasTimezone && dateStr.includes('T')) {
        // 没有时区后缀的 ISO 格式，当作 UTC 处理
        // 重新解析，添加 Z 后缀
        return new Date(dateStr + 'Z');
    }
    return date;
}

function formatTime(dateString) {
    const date = parseUTCDate(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    if (diffDays < 7) return `${diffDays}天前`;
    return date.toLocaleDateString('zh-CN');
}

// 侧边栏切换
function toggleSidebar() {
    landingSidebar.classList.toggle('open');
    // 更新按钮图标方向
    const toggleBtn = document.getElementById('sidebarToggle');
    if (toggleBtn) {
        const svg = toggleBtn.querySelector('svg');
        if (landingSidebar.classList.contains('open')) {
            // 展开状态：显示收起图标（向左箭头）
            svg.innerHTML = '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="15" y1="3" x2="15" y2="21"></line>';
        } else {
            // 收起状态：显示展开图标（向右箭头）
            svg.innerHTML = '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line>';
        }
    }
}

// 新建会话（从首页）
async function createNewSessionFromLanding() {
    const now = new Date();
    const timestamp = now.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
    const title = `会话 ${timestamp}`;

    try {
        const session = await api.createSession(title);
        // 跳转到聊天工作台
        window.location.href = `/chat/${session.id}`;
    } catch (error) {
        console.error('Failed to create session:', error);
        alert('创建会话失败: ' + error.message);
    }
}

// 登出处理
async function handleLogout() {
    try {
        await api.logout();
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        localStorage.removeItem('access_token');
        currentUser = null;
        updateHeaderUI();
        // 清空会话列表
        sessionsList.innerHTML = '';
        // 关闭侧边栏
        landingSidebar.classList.remove('open');
    }
}

// Setup all event listeners
function setupEventListeners() {
    // Form submission
    mainForm.addEventListener('submit', handleMainSubmit);

    // Keyboard: Enter to submit, Shift+Enter for new line
    mainInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (mainInput.value.trim() && !sendBtn.disabled) {
                mainForm.dispatchEvent(new Event('submit'));
            }
        }
    });

    // Example tags
    examples.forEach(tag => {
        tag.addEventListener('click', handleExampleClick);
    });

    // Modal controls
    modalOverlay.addEventListener('click', hideModal);
    modalClose.addEventListener('click', hideModal);

    // Tab switching
    authTabs.forEach(tab => {
        tab.addEventListener('click', handleTabSwitch);
    });

    // Modal forms
    document.getElementById('modalLoginForm').addEventListener('submit', handleModalLogin);
    document.getElementById('modalRegisterForm').addEventListener('submit', handleModalRegister);

    // Header and Sidebar events
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', toggleSidebar);
    }
    if (newSessionBtn) {
        newSessionBtn.addEventListener('click', createNewSessionFromLanding);
    }
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
}

// Handle main form submission
async function handleMainSubmit(e) {
    e.preventDefault();

    const content = mainInput.value.trim();
    if (!content) return;

    // Check authentication
    if (!currentUser) {
        // Show modal for unauthenticated users
        pendingInput = content;
        showModal();
        return;
    }

    // Authenticated: create session and redirect
    await createSessionAndRedirect(content);
}

// Handle example tag click
function handleExampleClick(e) {
    const text = this.getAttribute('data-text');
    mainInput.value = text;
    mainInput.focus();

    // Trigger submission
    mainForm.dispatchEvent(new Event('submit'));
}

// Create session and redirect to workspace
async function createSessionAndRedirect(content) {
    try {
        // Show loading state
        sendBtn.disabled = true;
        sendBtn.innerHTML = `
            <svg class="spin" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
        `;

        // Generate session title from content
        const title = content.length > 30 ? content.substring(0, 30) + '...' : content;

        // Create session
        const session = await api.createSession(title);

        // Store pending message
        localStorage.setItem('pending_message', content);

        // Redirect to workspace
        window.location.href = `/chat/${session.id}`;
    } catch (error) {
        console.error('Failed to create session:', error);
        alert('创建会话失败: ' + error.message);
    } finally {
        // Reset button
        sendBtn.disabled = false;
        sendBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 2L11 13"/>
                <path d="M22 2l-7 20-4-9-9-4 20-7z"/>
            </svg>
        `;
    }
}

// Modal functions
function showModal() {
    authModal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function hideModal() {
    authModal.classList.add('hidden');
    document.body.style.overflow = '';

    // Clear forms
    document.getElementById('modalLoginForm').reset();
    document.getElementById('modalRegisterForm').reset();
    document.getElementById('loginError').textContent = '';
    document.getElementById('registerError').textContent = '';
}

function handleTabSwitch(e) {
    const tabName = e.target.getAttribute('data-tab');

    // Update tab active states
    authTabs.forEach(tab => {
        if (tab === e.target) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Update content visibility
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    if (tabName === 'login') {
        document.getElementById('loginTab').classList.add('active');
    } else {
        document.getElementById('registerTab').classList.add('active');
    }

    // Clear errors
    document.getElementById('loginError').textContent = '';
    document.getElementById('registerError').textContent = '';
}

// Handle modal login
async function handleModalLogin(e) {
    e.preventDefault();

    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');

    try {
        errorDiv.textContent = '';
        await api.login(username, password);
        currentUser = await checkAuthStatus();

        // Hide modal and update UI
        hideModal();
        updateHeaderUI();
        loadSessions();

        if (pendingInput) {
            await createSessionAndRedirect(pendingInput);
        }
    } catch (error) {
        errorDiv.textContent = error.message || '登录失败';
    }
}

// Handle modal register
async function handleModalRegister(e) {
    e.preventDefault();

    const username = document.getElementById('registerUsername').value;
    const email = document.getElementById('registerEmail').value;
    const password = document.getElementById('registerPassword').value;
    const confirmPassword = document.getElementById('registerConfirmPassword').value;
    const errorDiv = document.getElementById('registerError');

    // Validation
    if (password !== confirmPassword) {
        errorDiv.textContent = '密码不一致';
        return;
    }

    if (password.length < 6) {
        errorDiv.textContent = '密码至少6位';
        return;
    }

    try {
        errorDiv.textContent = '';
        await api.register(username, email, password);
        // Auto login after registration
        await api.login(username, password);
        currentUser = await checkAuthStatus();

        // Hide modal and update UI
        hideModal();
        updateHeaderUI();
        loadSessions();

        if (pendingInput) {
            await createSessionAndRedirect(pendingInput);
        }
    } catch (error) {
        errorDiv.textContent = error.message || '注册失败';
    }
}

// Initialize on page load
initLanding();
