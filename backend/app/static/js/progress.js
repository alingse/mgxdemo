/**
 * ProgressTracker - AI 执行进度追踪器
 *
 * 轮询后端 API 获取执行步骤，并通过回调函数更新 UI
 */
class ProgressTracker {
    /**
     * 构造函数
     * @param {string} sessionId - 会话 ID
     * @param {function} onUpdate - 更新回调 (steps) => void
     * @param {function} onComplete - 完成回调 (success, data) => void
     */
    constructor(sessionId, onUpdate, onComplete) {
        this.sessionId = sessionId;
        this.onUpdate = onUpdate;
        this.onComplete = onComplete;

        this.isPolling = false;
        this.pollInterval = 1000; // 1 秒轮询间隔
        this.timeoutId = null;
        this.errorCount = 0;
        this.maxErrors = 5;
        this.startTime = null;
        this.timeoutMs = 5 * 60 * 1000; // 5 分钟超时
    }

    /**
     * 启动轮询
     */
    start() {
        if (this.isPolling) return;

        this.isPolling = true;
        this.startTime = Date.now();
        console.log('[ProgressTracker] Started polling for session:', this.sessionId);

        this.poll();
    }

    /**
     * 停止轮询
     */
    stop() {
        if (!this.isPolling) return;

        this.isPolling = false;
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
        console.log('[ProgressTracker] Stopped polling');
    }

    /**
     * 执行单次轮询
     */
    async poll() {
        if (!this.isPolling) return;

        // 检查超时
        if (Date.now() - this.startTime > this.timeoutMs) {
            console.warn('[ProgressTracker] Timeout after', this.timeoutMs, 'ms');
            this.stop();
            this.onComplete(false, { message: 'Polling timeout' });
            return;
        }

        try {
            // 获取最新执行步骤
            const steps = await api.getLatestExecutionSteps(this.sessionId);

            // 重置错误计数
            this.errorCount = 0;

            // 如果没有步骤，继续轮询
            if (!steps || steps.length === 0) {
                this.scheduleNext();
                return;
            }

            // 调用 UI 更新回调
            this.onUpdate(steps);

            // 检查是否完成
            const latest = steps[steps.length - 1];
            if (latest.status === 'completed' || latest.status === 'failed') {
                console.log('[ProgressTracker] Execution finished:', latest.status);
                this.stop();
                this.onComplete(true, latest);
                return;
            }

            // 继续轮询
            this.scheduleNext();

        } catch (error) {
            console.error('[ProgressTracker] Polling error:', error);
            this.errorCount++;

            if (this.errorCount >= this.maxErrors) {
                console.warn('[ProgressTracker] Too many errors, stopping');
                this.stop();
                this.onComplete(false, error);
            } else {
                // 指数退避重试
                this.scheduleNext(true);
            }
        }
    }

    /**
     * 安排下次轮询
     * @param {boolean} backoff - 是否使用退避策略
     */
    scheduleNext(backoff = false) {
        if (!this.isPolling) return;

        let delay = this.pollInterval;

        // 指数退避：1s -> 2s -> 4s
        if (backoff) {
            const backoffLevel = Math.min(this.errorCount, 3);
            delay = this.pollInterval * Math.pow(2, backoffLevel);
        }

        this.timeoutId = setTimeout(() => {
            this.poll();
        }, delay);
    }

    /**
     * 等待完成（返回 Promise）
     * @returns {Promise<{success: boolean, data: any}>}
     */
    waitForCompletion() {
        return new Promise((resolve) => {
            const originalOnComplete = this.onComplete;
            this.onComplete = (success, data) => {
                if (originalOnComplete) {
                    originalOnComplete(success, data);
                }
                resolve({ success, data });
            };
        });
    }
}
