// Auth functions

async function handleLogin(e) {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('error');

    try {
        errorDiv.textContent = '';
        await api.login(username, password);

        // Check if there's an intended URL
        const intendedUrl = localStorage.getItem('intended_url');
        localStorage.removeItem('intended_url');

        if (intendedUrl && intendedUrl.startsWith('/chat/')) {
            window.location.href = intendedUrl;
        } else {
            window.location.href = '/';
        }
    } catch (error) {
        errorDiv.textContent = error.message || '登录失败';
    }
}

async function handleRegister(e) {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const errorDiv = document.getElementById('error');

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

        // Check if there's an intended URL
        const intendedUrl = localStorage.getItem('intended_url');
        localStorage.removeItem('intended_url');

        if (intendedUrl && intendedUrl.startsWith('/chat/')) {
            window.location.href = intendedUrl;
        } else {
            window.location.href = '/';
        }
    } catch (error) {
        errorDiv.textContent = error.message || '注册失败';
    }
}

async function handleLogout() {
    try {
        await api.logout();
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        api.setToken(null);
        window.location.href = '/';  // Redirect to landing page
    }
}

// Check auth on page load
async function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        return false;
    }

    try {
        const user = await api.getCurrentUser();
        return user;
    } catch (error) {
        api.setToken(null);
        return false;
    }
}
