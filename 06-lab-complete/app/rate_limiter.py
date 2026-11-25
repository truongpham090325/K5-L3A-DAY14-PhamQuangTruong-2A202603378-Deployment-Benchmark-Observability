"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_client

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """
    Sliding window 60 giây dùng Redis sorted set.

    Mỗi request là một phần tử trong sorted set có score = timestamp.
    Các bước: ZREMRANGEBYSCORE (xoá request cũ) → ZCARD (đếm)
    → nếu vượt giới hạn raise 429 → ZADD + EXPIRE (thêm request hiện tại).
    """
    client = get_client()
    if client is None:
        # Không có Redis thì không chặn được theo cụm; vẫn cho đi tiếp
        # (kiểm tra 429 thật cần Redis, như trong hợp đồng).
        return

    now = time.time()
    window_start = now - WINDOW_SECONDS
    zkey = f"rate_limit:{key}"

    # Member duy nhất cho mỗi request để tránh ghi đè trong cùng 1 giây
    member = f"{now:.6f}:{uuid.uuid4().hex}"

    try:
        pipe = client.pipeline(transaction=True)
        pipe.zremrangebyscore(zkey, 0, window_start)
        pipe.zcard(zkey)
        _, count = pipe.execute()
    except Exception:
        # Redis lỗi: fail-open để không chặn nhầm toàn bộ traffic.
        return

    limit = settings.rate_limit_per_minute
    if count >= limit:
        retry_after = max(1, int(window_start + WINDOW_SECONDS - now) + 1)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        client.zadd(zkey, {member: now})
        client.expire(zkey, WINDOW_SECONDS)
    except Exception:
        pass
