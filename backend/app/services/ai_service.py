from app.config import get_settings
from app.services.base import AIService
from app.services.deepseek_service import DeepSeekService

settings = get_settings()


def get_ai_service(provider: str | None = None, enable_reasoning: bool = True) -> AIService:
    """获取 DeepSeek AI 服务实例

    Args:
        provider: AI 提供商（忽略，始终使用 DeepSeek）
        enable_reasoning: 是否启用思考模式（默认 True）

    Returns:
        DeepSeekService 实例
    """
    if not settings.deepseek_api_key:
        raise ValueError("DeepSeek API key 未配置，请在 .env 文件中设置 DEEPSEEK_API_KEY")

    return DeepSeekService(enable_reasoning=enable_reasoning)
