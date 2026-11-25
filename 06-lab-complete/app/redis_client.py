"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Yêu cầu:
  • Đọc REDIS_URL từ config
  • App vẫn phải KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng (đừng ping Redis lúc import)
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False
"""
import redis

from app.config import settings

_client: redis.Redis | None = None


def get_client() -> "redis.Redis | None":
    """
    Trả về Redis client (tạo lần đầu, tái sử dụng các lần sau).

    redis.from_url không kết nối ngay (lazy), nên việc import / tạo client
    không bao giờ làm app crash khi Redis chưa chạy. Trả None nếu REDIS_URL rỗng.
    """
    global _client
    if _client is None:
        url = settings.redis_url
        if not url:
            return None
        try:
            _client = redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
        except Exception:
            return None
    return _client


def redis_healthy() -> bool:
    """Dùng cho GET /ready. Redis không kết nối được → False."""
    client = get_client()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False
