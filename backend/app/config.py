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
    tool_execution_timeout: int = 30  # seconds
    max_tool_calls_per_message: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
