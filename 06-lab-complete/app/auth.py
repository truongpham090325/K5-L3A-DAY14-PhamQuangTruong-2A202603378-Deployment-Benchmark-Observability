"""
API Key authentication (tiêu chí 6).

Yêu cầu:
  • Client gửi header  X-API-Key: <key>
  • Key phải trùng biến môi trường AGENT_API_KEY
  • Thiếu hoặc sai key → HTTP 401 (không phải 403 hay 422)
"""
import secrets

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

# auto_error=False để tự trả 401 thay vì 422 khi thiếu header
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    """
    Dependency cho FastAPI — dùng trong /ask: Depends(verify_api_key).

    Trả về API key nếu hợp lệ, ngược lại raise HTTPException(401).
    Dùng secrets.compare_digest để so sánh an toàn (tránh timing attack).
    """
    expected = settings.agent_api_key
    if not expected or not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return api_key
