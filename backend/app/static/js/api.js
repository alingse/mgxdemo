// API base URL
const API_BASE = window.location.origin;

// API client
class ApiClient {
    constructor() {
        this.token = localStorage.getItem('access_token');
    }

    setToken(token) {
        this.token = token;
        if (token) {
            localStorage.setItem('access_token', token);
        } else {
            localStorage.removeItem('access_token');
        }
    }

    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        return headers;
    }

    async request(url, options = {}) {
        const config = {
            ...options,
            headers: {
                ...this.getHeaders(),
                ...options.headers
            }
        };

        const response = await fetch(`${API_BASE}${url}`, config);

        if (response.status === 401) {
            // Unauthorized - clear token and redirect to login
            this.setToken(null);
            if (window.location.pathname !== '/sign-in') {
                window.location.href = '/sign-in';
            }
            throw new Error('Unauthorized');
        }

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }

        // For 204 No Content
        if (response.status === 204) {
            return null;
        }

        return response.json();
    }

    // Auth APIs
    async register(username, email, password) {
        return this.request('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password })
        });
    }

    async login(username, password) {
        const data = await this.request('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        if (data.access_token) {
            this.setToken(data.access_token);
        }
        return data;
    }

    async getCurrentUser() {
        return this.request('/api/auth/me');
    }

    async logout() {
        return this.request('/api/auth/logout', {
            method: 'POST'
        });
    }

    // Session APIs
    async listSessions() {
        return this.request('/api/sessions');
    }

    async createSession(title) {
        return this.request('/api/sessions', {
            method: 'POST',
            body: JSON.stringify({ title })
        });
    }

    async getSession(sessionId) {
        return this.request(`/api/sessions/${sessionId}`);
    }

    async deleteSession(sessionId) {
        return this.request(`/api/sessions/${sessionId}`, {
            method: 'DELETE'
        });
    }

    async updateSession(sessionId, updates) {
        return this.request(`/api/sessions/${sessionId}`, {
            method: 'PUT',
            body: JSON.stringify(updates)
        });
    }

    // Message APIs
    async listMessages(sessionId) {
        return this.request(`/api/sessions/${sessionId}/messages`);
    }

    async createMessage(sessionId, content) {
        return this.request(`/api/sessions/${sessionId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ content })
        });
    }

    // Sandbox APIs
    async listFiles(sessionId) {
        return this.request(`/api/sessions/${sessionId}/sandbox/files`);
    }

    async getFile(sessionId, filename) {
        return this.request(`/api/sessions/${sessionId}/sandbox/files/${filename}`);
    }

    async updateFile(sessionId, filename, content) {
        return this.request(`/api/sessions/${sessionId}/sandbox/files/${filename}`, {
            method: 'POST',
            body: JSON.stringify({ content })
        });
    }

    getPreviewUrl(sessionId) {
        return `${API_BASE}/api/sessions/${sessionId}/sandbox/preview`;
    }

    getStaticUrl(sessionId, filename) {
        return `${API_BASE}/api/sessions/${sessionId}/sandbox/static/${filename}`;
    }

    // Execution Progress APIs
    async getLatestExecutionSteps(sessionId) {
        return this.request(`/api/sessions/${sessionId}/messages/_internal/latest/execution-steps`);
    }

    async getExecutionSteps(sessionId, messageId) {
        return this.request(`/api/sessions/${sessionId}/messages/${messageId}/execution-steps`);
    }

    async getTodos(sessionId) {
        return this.request(`/api/sessions/${sessionId}/todos`);
    }
}

// Create global API client instance
const api = new ApiClient();
