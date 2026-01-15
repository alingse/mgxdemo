"""Server-Sent Events (SSE) utilities."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)


class SSEEvent:
    """SSE事件封装"""

    @staticmethod
    def format(data: Any, event: str = None, id: str = None) -> str:
        """格式化SSE事件

        Args:
            data: 事件数据（会被转换为JSON）
            event: 事件类型
            id: 事件ID

        Returns:
            格式化的SSE事件字符串
        """
        lines = []

        if id:
            lines.append(f"id: {id}")

        if event:
            lines.append(f"event: {event}")

        # 转换为JSON字符串
        if isinstance(data, dict):
            data_str = json.dumps(data, ensure_ascii=False)
        else:
            data_str = str(data)

        # 多行数据每行都要有 data: 前缀
        for line in data_str.split("\n"):
            lines.append(f"data: {line}")

        lines.append("")  # 空行表示事件结束
        return "\n".join(lines) + "\n"


async def stream_sse(
    event_generator: AsyncGenerator[dict, None], ping_interval: int = 15
) -> StreamingResponse:
    """创建SSE流响应

    Args:
        event_generator: 异步事件生成器，yield格式: {"data": dict, "event": str, "id": str}
        ping_interval: 心跳间隔（秒），防止连接超时

    Returns:
        StreamingResponse对象
    """

    async def event_stream():
        try:
            async for event in event_generator:
                yield SSEEvent.format(**event)

            # 发送完成事件
            yield SSEEvent.format(data={"done": True}, event="done")

        except Exception as e:
            logger.error(f"[SSE] Error in event stream: {e}", exc_info=True)
            # 发送错误事件
            yield SSEEvent.format(data={"error": str(e)}, event="error")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
        },
    )
