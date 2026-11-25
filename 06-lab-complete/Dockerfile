# ============================================================
# Production Dockerfile — multi-stage build (tiêu chí 1)
#   • Stage builder : cài dependencies (pip install --user)
#   • Stage runtime : base slim, user non-root, HEALTHCHECK
#   • CMD dùng exec form + ${PORT:-8000}, uvicorn là PID 1
#     để nhận SIGTERM khi `docker stop` (graceful shutdown)
# ============================================================

# ── Stage 1: builder — cài dependencies ──
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Copy requirements trước để tận dụng Docker layer cache
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy source code
COPY app/ ./app/
COPY utils/ ./utils/


# ── Stage 2: runtime — chỉ copy kết quả, chạy user non-root ──
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUSERBASE=/home/appuser/.local \
    PATH="/home/appuser/.local/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"

# Tạo user non-root
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# Copy dependencies đã cài (pip install --user → /root/.local) sang home appuser
COPY --from=builder /root/.local /home/appuser/.local
# Copy source code
COPY --from=builder /build/app ./app
COPY --from=builder /build/utils ./utils

RUN chown -R appuser:appuser /home/appuser /app

USER appuser

EXPOSE 8000

# HEALTHCHECK gọi GET /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"]

# exec + uvicorn là PID 1 để nhận SIGTERM khi `docker stop`; lắng nghe theo ${PORT:-8000}
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
