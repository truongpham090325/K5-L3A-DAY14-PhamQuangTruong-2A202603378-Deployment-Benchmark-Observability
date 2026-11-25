"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.

Các biến được đọc (có giá trị mặc định hợp lý khi chạy local):
    PORT, ENVIRONMENT, AGENT_API_KEY, REDIS_URL,
    RATE_LIMIT_PER_MINUTE, DAILY_BUDGET_USD, MONTHLY_BUDGET_USD

Không hard-code secret nào trong code — API key thật luôn nằm trong env.
"""
import os
from dataclasses import dataclass, field


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # Server
    port: int = field(default_factory=lambda: _get_int("PORT", 8000))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # Security — API key được cấp qua môi trường, không ghi trong code
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))

    # Redis
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # Rate limiting
    rate_limit_per_minute: int = field(default_factory=lambda: _get_int("RATE_LIMIT_PER_MINUTE", 10))

    # Cost guard (đơn vị USD)
    daily_budget_usd: float = field(default_factory=lambda: _get_float("DAILY_BUDGET_USD", 1.0))
    monthly_budget_usd: float = field(default_factory=lambda: _get_float("MONTHLY_BUDGET_USD", 0.0))


settings = Settings()
