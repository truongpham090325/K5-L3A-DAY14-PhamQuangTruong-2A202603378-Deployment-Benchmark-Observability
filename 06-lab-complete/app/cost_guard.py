"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_client

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_DAILY_KEY = "cost:daily:{date}"
_MONTHLY_KEY = "cost:monthly:{ym}"


def _keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    daily = _DAILY_KEY.format(date=now.strftime("%Y-%m-%d"))
    monthly = _MONTHLY_KEY.format(ym=now.strftime("%Y-%m"))
    return daily, monthly


def _spent(key: str) -> float:
    client = get_client()
    if client is None:
        return 0.0
    try:
        return float(client.get(key) or 0.0)
    except Exception:
        return 0.0


def check_budget() -> None:
    """
    Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402).
    """
    daily_key, monthly_key = _keys()

    if settings.daily_budget_usd > 0 and _spent(daily_key) >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")

    if settings.monthly_budget_usd > 0 and _spent(monthly_key) >= settings.monthly_budget_usd:
        raise HTTPException(status_code=402, detail="Monthly budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request.
    """
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + \
           (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K

    client = get_client()
    if client is None:
        return cost

    daily_key, monthly_key = _keys()
    try:
        pipe = client.pipeline(transaction=True)
        pipe.incrbyfloat(daily_key, cost)
        pipe.expire(daily_key, 2 * 24 * 3600)
        pipe.incrbyfloat(monthly_key, cost)
        pipe.expire(monthly_key, 32 * 24 * 3600)
        pipe.execute()
    except Exception:
        pass

    return cost
