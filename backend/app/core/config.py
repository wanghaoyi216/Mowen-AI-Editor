import os
import warnings
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# 模型 ID（NVIDIA NIM 端点，已用 /v1/models 接口验证存在）
#   端点：https://integrate.api.nvidia.com/v1
#   key 形如 nvapi-...（NVIDIA NIM 平台 token）
# 主创作：Nemotron 3 Ultra 550B
# 子 Agent：MiniMax 2.7
NVIDIA_WRITING_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
NVIDIA_SUBAGENT_MODEL = "minimaxai/minimax-m2.7"


class Settings(BaseSettings):
    app_name: str = "Novel AI Editor API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    # CORS 允许的源，逗号分隔（示例："http://a.example.com,http://b.example.com"）
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")
    # 开发默认 sqlite，生产必须通过 DATABASE_URL 覆盖
    database_url: str = Field(
        default="sqlite+aiosqlite:///./novel_ai_editor.db",
        validation_alias="DATABASE_URL",
    )
    firecrawl_key: str | None = None
    tavily_key: str | None = None
    # NVIDIA NIM 端点（OpenAI 兼容协议）。key 形如 nvapi-...，环境变量 NVIDIA_API_KEY
    nvidia_api_key: str | None = Field(default=None, validation_alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        validation_alias="NVIDIA_BASE_URL",
    )
    nvidia_primary_model: str = Field(default=NVIDIA_WRITING_MODEL, validation_alias="NVIDIA_PRIMARY_MODEL")
    nvidia_fallback_models: str = Field(
        default=(
            "nvidia/nemotron-3-ultra-550b-a55b,minimaxai/minimax-m2.7,"
            "nvidia/llama-3.1-nemotron-70b-instruct,meta/llama-3.1-70b-instruct"
        ),
        validation_alias="NVIDIA_FALLBACK_MODELS",
    )
    rate_limit_calls_per_minute: int = Field(default=40, validation_alias="RATE_LIMIT_CALLS_PER_MINUTE")
    external_request_retries: int = 5
    external_request_timeout_seconds: int = 120
    llm_request_timeout_seconds: int = 300
    task_runtime_cache_ttl_seconds: int = 3600
    # JWT 密钥：开发默认自动生成（可重启即变），生产必须显式设置 SECRET_KEY
    secret_key: str = Field(default="", validation_alias="SECRET_KEY")
    neo4j_uri: str = Field(default="bolt://neo4j:7687", validation_alias="NEO4J_URI")
    neo4j_database: str = Field(default="neo4j", validation_alias="NEO4J_DATABASE")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", validation_alias="NEO4J_PASSWORD")

    # AI Diversity Engine Settings
    # creator = 主创作模型（写正文，长上下文 Nemotron）
    # controller = 子 Agent / 控制模型（规划、审稿、一致性，使用 MiniMax M2.7）
    creator_model: str = Field(default=NVIDIA_WRITING_MODEL, validation_alias="CREATOR_MODEL", description="主创作模型（正文）")
    controller_model: str = Field(default=NVIDIA_SUBAGENT_MODEL, validation_alias="CONTROLLER_MODEL", description="子 Agent / 控制模型（MiniMax M2.7）")
    embedding_model: str = Field(default="nvidia/embed-qa-4", description="Embedding 模型")
    creator_temperature: float = Field(default=1.0, description="创作模型默认温度")
    controller_temperature: float = Field(default=0.4, description="控制模型默认温度")
    similarity_threshold: float = Field(default=0.85, description="内容相似度阈值")
    style_diversity_threshold: float = Field(default=0.8, description="风格多样性阈值")
    # Nemotron 3 Ultra 550B 是 reasoning model，必须传 enable_thinking
    # + reasoning_budget，否则 NVIDIA 后端会一直 thinking 不返回
    nvidia_enable_thinking: bool = Field(default=True, validation_alias="NVIDIA_ENABLE_THINKING", description="NVIDIA reasoning 模型是否开启 thinking")
    nvidia_reasoning_budget: int = Field(default=16384, validation_alias="NVIDIA_REASONING_BUDGET", description="NVIDIA reasoning 模型 thinking token 预算")
    nvidia_top_p: float = Field(default=0.95, validation_alias="NVIDIA_TOP_P", description="NVIDIA 模型 top_p")
    # Nemotron reasoning 模型 output token 预算。**注意：必须大于 reasoning_budget**，
    # 否则 thinking 阶段会耗光 max_tokens，output 被截断导致 JSON 解析失败。
    nvidia_max_output_tokens: int = Field(default=32768, validation_alias="NVIDIA_MAX_OUTPUT_TOKENS", description="NVIDIA reasoning 模型 output 阶段 max_tokens")
    # 整体请求超时（秒）。reasoning model thinking 阶段 1-5 分钟，主模型给 600s；
    # fallback 是普通模型，30-60s 足够。
    nvidia_primary_request_timeout_seconds: float = Field(default=600.0, validation_alias="NVIDIA_PRIMARY_REQUEST_TIMEOUT_SECONDS", description="主模型整体请求超时")
    nvidia_fallback_request_timeout_seconds: float = Field(default=60.0, validation_alias="NVIDIA_FALLBACK_REQUEST_TIMEOUT_SECONDS", description="fallback 模型整体请求超时")
    # 首字节超时（秒）：建立连接后 N 秒内没收到任何 SSE 数据行 → 切下一个模型。
    # 之前硬编码 10/20，现在暴露到 .env，方便 NVIDIA 限流时调小。
    nvidia_primary_first_byte_timeout_seconds: float = Field(default=10.0, validation_alias="NVIDIA_PRIMARY_FIRST_BYTE_TIMEOUT_SECONDS", description="主模型首字节超时")
    nvidia_fallback_first_byte_timeout_seconds: float = Field(default=20.0, validation_alias="NVIDIA_FALLBACK_FIRST_BYTE_TIMEOUT_SECONDS", description="fallback 模型首字节超时")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

# 启动时对 secret_key 做兜底：空值则本地会话内随机生成（开发友好），生产强制拒绝
_env = os.environ.get("ENV", os.environ.get("NODE_ENV", "")).lower()
is_production = _env in ("production", "prod")

if not settings.secret_key:
    if is_production:
        raise RuntimeError(
            "SECURITY ERROR: SECRET_KEY environment variable is required in production. "
            "Generate a strong secret via: python -c \"import secrets; print(secrets.token_urlsafe(64))\" "
            "then set it in your .env file or container environment."
        )
    # 开发模式：自动生成临时密钥（重启即失效）
    settings.secret_key = secrets.token_urlsafe(48)

if settings.secret_key == "changeme":
    warnings.warn(
        "CRITICAL SECURITY WARNING: secret_key is using the legacy default 'changeme'. "
        "Replace it with a strong random secret via SECRET_KEY environment variable.",
        UserWarning,
        stacklevel=2,
    )
