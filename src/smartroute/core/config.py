"""
SmartRoute Agent 配置管理模块

支持从环境变量和 YAML 配置文件加载配置
"""

import os
from pathlib import Path
from typing import Any

# 加载 .env 文件到环境变量
from dotenv import load_dotenv
_load_env_result = load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderSettings(BaseSettings):
    """LLM 供应商配置"""

    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = Field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_model_default: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL_DEFAULT", "glm-5"))
    openai_model_gpt4o: str = "gpt-4o"
    openai_model_gpt4o_mini: str = "gpt-4o-mini"

    anthropic_api_key: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_base_url: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
    anthropic_model_claude: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL_CLAUDE", "deepseek-v4-pro"))
    anthropic_model_sonnet: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL_SONNET", "deepseek-v4-flash"))

    qwen_api_key: str = Field(default_factory=lambda: os.getenv("QWEN_API_KEY", ""))
    qwen_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    qwen_model: str = "qwen-max"


class DatabaseSettings(BaseSettings):
    """数据库配置"""

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "smartroute"
    postgres_password: str = ""
    postgres_db: str = "smartroute"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_poi: str = "poi_embeddings"
    milvus_collection_user: str = "user_profiles"

    es_host: str = "localhost"
    es_port: int = 9200
    es_user: str = "elastic"
    es_password: str = ""

    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_db: str = "smartroute_logs"


class ExternalAPISettings(BaseSettings):
    """外部 API 配置"""

    amap_api_key: str = ""
    amap_base_url: str = "https://restapi.amap.com/v3"

    dianping_api_key: str = ""
    dianping_base_url: str = "https://api.dianping.com/v1"

    qweather_api_key: str = ""
    qweather_base_url: str = "https://api.qweather.com/v7"


class AppSettings(BaseSettings):
    """应用配置"""

    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Session 配置
    session_ttl_seconds: int = 86400
    session_redis_prefix: str = "session:"

    # 缓存配置
    ugc_cache_ttl_seconds: int = 604800
    poi_cache_ttl_seconds: int = 3600

    # 性能参数
    llm_timeout_seconds: int = 10
    route_solve_timeout_seconds: int = 2
    stream_first_token_target_seconds: int = 2

    # 召回配置
    retrieval_top_k: int = 50
    candidate_pool_size: int = 20
    route_plan_count: int = 3
    max_poi_overlap_ratio: float = 0.5

    # 成本控制
    llm_budget_per_request_yuan: float = 0.20
    budget_alert_ratio: float = 1.2

    # 监控
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "smartroute-agent"
    prometheus_port: int = 9090


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
        env_nested_delimiter="__",
    )

    llm: LLMProviderSettings = Field(default_factory=LLMProviderSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: ExternalAPISettings = Field(default_factory=ExternalAPISettings)
    app: AppSettings = Field(default_factory=AppSettings)

    # YAML 配置文件路径
    yaml_config_path: str = "config/settings.yaml"
    implicit_rules_path: str = "config/implicit_rules.yaml"

    # 加载的 YAML 配置
    _yaml_config: dict[str, Any] = {}

    def load_yaml_config(self) -> None:
        """加载 YAML 配置文件"""
        config_path = Path(self.yaml_config_path)
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as f:
                self._yaml_config = yaml.safe_load(f) or {}

    def get_agent_config(self, agent_name: str) -> dict[str, Any]:
        """获取指定 Agent 的配置"""
        agents_config = self._yaml_config.get("agents", {})
        return agents_config.get(agent_name, {})

    def get_llm_config(self) -> dict[str, Any]:
        """获取 LLM 配置"""
        return self._yaml_config.get("llm", {})

    def get_performance_targets(self) -> dict[str, Any]:
        """获取性能指标目标"""
        return self._yaml_config.get("performance", {})

    def get_evaluation_targets(self) -> dict[str, Any]:
        """获取评测指标目标"""
        return self._yaml_config.get("evaluation_targets", {})


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取全局配置实例"""
    if not settings._yaml_config:
        settings.load_yaml_config()
    return settings