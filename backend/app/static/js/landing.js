// Landing page state
let currentUser = null;
let pendingInput = '';

// DOM elements
const mainForm = document.getElementById('mainForm');
const mainInput = document.getElementById('mainInput');
const submitBtn = document.getElementById('submitBtn');
const authModal = document.getElementById('authModal');
const modalOverlay = document.getElementById('modalOverlay');
const modalClose = document.getElementById('modalClose');
const examples = document.querySelectorAll('.example-tag');
const authTabs = document.querySelectorAll('.auth-tab');

// Initialize landing page
async function initLanding() {
    // Check auth status
    currentUser = await checkAuth();

    // Setup event listeners
    setupEventListeners();
}

// Setup all event listeners
function setupEventListeners() {
    // Form submission
    mainForm.addEventListener('submit', handleMainSubmit);

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
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading-spinner"></span> 创建中...';

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
        submitBtn.disabled = false;
        submitBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
            开始创建
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
        currentUser = await checkAuth();

        // Hide modal and proceed with session creation
        hideModal();

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
        currentUser = await checkAuth();

        // Hide modal and proceed with session creation
        hideModal();

        if (pendingInput) {
            await createSessionAndRedirect(pendingInput);
        }
    } catch (error) {
        errorDiv.textContent = error.message || '注册失败';
    }
}

// Initialize on page load
initLanding();
