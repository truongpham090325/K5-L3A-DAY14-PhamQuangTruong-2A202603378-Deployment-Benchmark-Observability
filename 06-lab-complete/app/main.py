"""
Production AI Agent — Part 6 Final Project.

Đã hoàn thành đủ 12 tiêu chí trong README.md:
  /health (liveness), /ready (readiness), API key auth,
  rate limiting (Redis), cost guard (Redis), config từ env,
  structured JSON logging, graceful shutdown (lifespan + uvicorn).
Kiểm tra: python check_production_ready.py
"""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ─────────────────────────────────────────────────────────
# Structured JSON logging (tiêu chí 10)
# ─────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    """Mỗi dòng log là 1 JSON object hợp lệ."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _setup_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    log = logging.getLogger("agent")
    log.setLevel(logging.INFO)
    log.handlers = [handler]
    log.propagate = False
    return log


logger = _setup_logging()


def log(event: str, **fields) -> None:
    logger.info(event, extra={"fields": fields})


# ─────────────────────────────────────────────────────────
# Lifespan — graceful shutdown (tiêu chí 11)
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log("startup", environment=settings.environment, port=settings.port)
    yield
    # uvicorn tự xử lý SIGTERM: ngừng nhận request mới, hoàn thành in-flight rồi thoát 0.
    log("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    log(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=elapsed_ms,
    )
    return response


# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None


# ─────────────────────────────────────────────────────────
# Health / Readiness (tiêu chí 4 & 5)
# ─────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness: luôn trả 200 khi process còn chạy, kể cả khi Redis chết."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: 200 khi sẵn sàng, 503 khi Redis không kết nối được."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"status": "ready"}


# ─────────────────────────────────────────────────────────
# Agent endpoint (tiêu chí 6, 7, 8)
# ─────────────────────────────────────────────────────────
@app.post("/ask")
def ask(
    body: AskRequest,
    api_key: str = Depends(verify_api_key),
):
    # Rate limiting (429) — state trong Redis, dùng chung cho mọi worker
    check_rate_limit(api_key)

    # Cost guard (402) — kiểm tra trước khi gọi LLM
    check_budget()

    answer = llm_ask(body.question)

    # Ước lượng token để ghi nhận chi phí sau khi gọi LLM
    input_tokens = max(1, len(body.question) // 4)
    output_tokens = max(1, len(answer) // 4)
    cost = record_cost(input_tokens, output_tokens)

    log("agent_answer", question_len=len(body.question), answer_len=len(answer))

    return {
        "question": body.question,
        "answer": answer,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "cost_usd": cost},
    }
