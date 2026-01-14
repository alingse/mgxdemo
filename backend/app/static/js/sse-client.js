/**
 * SSE客户端，用于监听服务器推送事件
 *
 * 特性：
 * - 支持Authorization header（使用fetch实现）
 * - 自动重连机制
 * - 心跳检测
 */
class SSEClient {
    constructor(sessionId, options = {}) {
        this.sessionId = sessionId;
        this.onEvent = options.onEvent || (() => {});
        this.onError = options.onError || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onSync = options.onSync || (() => {});

        this.isConnected = false;
        this.abortController = null;
        this.retryCount = 0;
        this.maxRetries = options.maxRetries || 3;
        this.retryDelay = options.retryDelay || 2000;
    }

    /**
     * 连接SSE流
     */
    async connect() {
        const url = `/api/sessions/${this.sessionId}/messages/stream`;
        const token = localStorage.getItem('access_token');

        this.abortController = new AbortController();

        try {
            const response = await fetch(url, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Accept': 'text/event-stream',
                },
                signal: this.abortController.signal
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.isConnected = true;
            this.retryCount = 0;
            console.log('[SSE] Connected to session', this.sessionId);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (this.isConnected) {
                const { done, value } = await reader.read();

                if (done) {
                    console.log('[SSE] Stream ended');
                    break;
                }

                buffer += decoder.decode(value, { stream: true });

                // 解析SSE事件
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // 保留不完整的消息

                for (const line of lines) {
                    if (line.trim()) {
                        this.parseSSEEvent(line);
                    }
                }
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[SSE] Connection aborted');
                return;
            }

            console.error('[SSE] Connection error:', error);
            this.isConnected = false;

            // 重试逻辑
            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                console.log(`[SSE] Retrying... (${this.retryCount}/${this.maxRetries})`);
                setTimeout(() => this.connect(), this.retryDelay * this.retryCount);
            } else {
                if (this.onError) {
                    this.onError(error);
                }
            }
        }
    }

    /**
     * 解析SSE事件
     */
    parseSSEEvent(text) {
        const lines = text.split('\n');
        let event = null;
        let data = null;
        let id = null;

        for (const line of lines) {
            if (line.startsWith('event:')) {
                event = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
                const dataStr = line.slice(5).trim();
                try {
                    data = JSON.parse(dataStr);
                } catch {
                    data = dataStr;
                }
            } else if (line.startsWith('id:')) {
                id = line.slice(3).trim();
            }
        }

        // 处理各种事件类型
        if (event === 'done' || data?.done) {
            console.log('[SSE] Stream completed');
            if (this.onComplete) {
                this.onComplete();
            }
            this.disconnect();
            return;
        }

        if (event === 'ping') {
            // 心跳，忽略
            return;
        }

        if (event === 'sync') {
            console.log('[SSE] Sync event:', data);
            if (this.onSync) {
                this.onSync(data);
            }
            return;
        }

        if (event === 'error' || data?.error) {
            console.error('[SSE] Error event:', data);
            if (this.onError) {
                this.onError(data?.error || 'Unknown error');
            }
            return;
        }

        // 业务事件（thinking, tool_calling等）
        if (this.onEvent && data) {
            this.onEvent({ event, data, id });
        }
    }

    /**
     * 断开连接
     */
    disconnect() {
        this.isConnected = false;
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
        console.log('[SSE] Disconnected');
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SSEClient;
}
