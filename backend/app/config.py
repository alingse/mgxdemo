from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # AI Service Configuration（仅支持 DeepSeek）
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    default_ai_provider: str = "deepseek"

    # Application Configuration
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Database Configuration
    database_url: str = "sqlite:///./agent_sandbox.db"

    # Sandbox Configuration
    sandbox_base_dir: str = "./sandboxes"
    max_sandbox_size_mb: int = 100
    max_file_size_mb: int = 1

    # Agent Loop Configuration
    enable_agent_loop: bool = True
    enable_streaming_reasoning: bool = True  # 启用流式推理内容传输
    tool_execution_timeout: int = 30  # seconds
    max_tool_calls_per_message: int = 10

    # Message Truncation Configuration
    max_user_input_length: int = 1000  # 用户输入最大字符数
    max_history_messages: int = 20  # 保留的历史消息数量
    enable_message_truncation: bool = True  # 是否启用消息截取
    truncation_warning_message: str = "...(消息已截取)"  # 截取提示文本

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
