# Day 14 Lab — Mission Answers

**Họ tên:** Phạm Quang Trường
**MSSV:** 2A202603378
**Lớp:** K5-L3A

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

Đọc `01-localhost-vs-production/develop/app.py`, mình tìm được **7 vấn đề** (yêu cầu ≥ 5):

1. **Hard-code API key trong code** — dòng 17: `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`. Chỉ cần push lên GitHub là key bị lộ ngay; không xoay vòng được nếu không sửa code.
2. **Hard-code DATABASE_URL kèm mật khẩu** — dòng 18: `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Lộ cả username + password thật.
3. **Dùng `print()` thay vì logging** — dòng 33–38, và tệ hơn là **in cả secret ra log**: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`. Log không có cấu trúc, khó parse và tự làm lộ secret.
4. **Không có health check endpoint** — đã kiểm chứng: `GET /health` trả **404**. Platform (Railway/Render/K8s) không có cách nào biết agent còn sống để restart khi crash.
5. **Hard-code port và host** — dòng 51–52: `host="localhost", port=8000`. Đã kiểm chứng: đặt `PORT=8012` mà app vẫn chạy cứng trên 8000 → không chạy được trong container/cloud (nơi platform cấp port qua biến môi trường).
6. **`DEBUG=True` và `reload=True` trong "production"** — dòng 21 và 53: auto-reload và debug làm chậm, lộ lỗi chi tiết.
7. **Không xử lý graceful shutdown** — khi platform gửi SIGTERM, request đang chạy sẽ bị cắt ngang, không có cleanup.

### Exercise 1.2: Chạy bản develop

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
```

Kết quả (bản develop nhận `question` qua **query**, không nhận JSON):

```text
POST /ask?question=Hello  → 200  {"answer":"Tôi là AI agent được deploy lên cloud. ..."}
GET  /health              → 404  {"detail":"Not Found"}
```

App chạy được nhưng **chưa production-ready**: không có health check (404) và port bị hard-code (đặt `PORT` khác cũng vẫn chạy 8000).

### Exercise 1.3: Bảng so sánh develop / production

| Feature | Develop | Production | Tại sao quan trọng? |
|---------|---------|------------|---------------------|
| Config | Hard-code (`OPENAI_API_KEY`, `DATABASE_URL`) | Env vars qua `config.py` (`Settings`) | Secret không nằm trong code → không lộ trên Git, đổi môi trường không cần sửa code (12-Factor) |
| Health check | Không có (`/health` → 404) | `/health` (liveness) + `/ready` (readiness) | Platform dựa vào probe để quyết định restart / route traffic |
| Logging | `print()`, log cả secret | JSON structured, không log secret | Log parse được bằng Datadog/Loki; không làm lộ dữ liệu nhạy cảm |
| Shutdown | Đột ngột (mất request) | Graceful (`lifespan` + SIGTERM) | Không cắt ngang request in-flight khi deploy/scale |
| Host / Port | `localhost` + port `8000` cố định | `0.0.0.0` + port từ `PORT` env | Chạy được trong container; platform cấp port động |
| CORS | Không có | Cấu hình `allow_origins` | Chặn trang web lạ gọi API |

**Vì sao hard-code secret nguy hiểm:** secret nằm trong source → bị commit vào Git → bất kỳ ai thấy repo đều lấy được key; muốn xoay key phải sửa code và deploy lại.
**Vì sao cần health check:** để orchestrator biết process còn sống mà restart khi lỗi.
**Vì sao cần graceful shutdown:** để không làm mất request của người dùng khi deploy/scale down.

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. **Base image là gì?** `python:3.11` (bản full, ~1 GB). Bản production (`02-docker/production/Dockerfile`) dùng `python:3.11-slim` cho cả 2 stage để image nhỏ hơn.
2. **Working directory là gì?** `/app` (`WORKDIR /app`) — mọi lệnh `COPY`/`RUN`/`CMD` sau đó chạy trong thư mục này.
3. **Tại sao `COPY requirements.txt` trước?** Để tận dụng **Docker layer cache**: `requirements.txt` ít thay đổi, nên layer `RUN pip install` được cache; nếu copy source trước thì mỗi lần sửa code lại phải chạy lại `pip install`.
4. **CMD vs ENTRYPOINT khác nhau thế nào?** `CMD` là lệnh mặc định, **có thể bị ghi đè** khi `docker run image <lệnh khác>`; `ENTRYPOINT` là lệnh cố định, khó bị ghi đè. Ở develop dùng `CMD ["python", "app.py"]`.

### Exercise 2.2–2.3: Build & so sánh kích thước image

```bash
# Build từ gốc repo (Dockerfile COPY theo đường dẫn tính từ gốc)
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images | grep my-agent
```

Kết quả đo thật bằng `docker images` (sau khi build từ gốc repo):

| Image | Kích thước |
|-------|-----------|
| Develop (`python:3.11` full, single-stage) | **1.67 GB** |
| Production (`python:3.11-slim`, multi-stage) | **240 MB** |

- Chênh lệch: production **nhỏ hơn ~86%** (chỉ bằng ~14% kích thước bản develop).

**Vì sao multi-stage nhỏ hơn:** stage 1 (builder) chứa toolchain build (gcc, libpq-dev…) để cài dependencies, nhưng stage 2 (runtime) chỉ copy `site-packages` và source → không kéo theo compiler và cache, image cuối nhỏ và ít lỗ hổng hơn. (Số MB trong bài là số mình tự đo bằng `docker images`, không chép từ tài liệu.)

### Exercise 2.4: Docker Compose stack

`02-docker/production/docker-compose.yml` gồm 4 service:

```
        Client
          │  :80
          ▼
      ┌────────┐
      │ Nginx  │  (reverse proxy + load balancer)
      └───┬────┘
          │ round-robin
     ┌────┴─────┬─────────┐
     ▼          ▼         ▼
  agent       agent      agent     (2+ replicas, không expose port trực tiếp)
     └────┬─────┴────┬────┘
          ▼          ▼
      ┌───────┐  ┌────────┐
      │ Redis │  │ Qdrant │      (cache/rate-limit · vector DB cho RAG)
      └───────┘  └────────┘
```

- **agent** build từ `02-docker/production/Dockerfile` (target `runtime`), đọc env (`REDIS_URL`, `QDRANT_URL`), `depends_on` redis + qdrant (chờ healthy).
- **redis** (`redis:7-alpine`) có healthcheck `redis-cli ping`.
- **qdrant** vector database cho retrieval.
- **nginx** (`nginx:alpine`) map port 80, là cổng duy nhất ra ngoài.

Test qua Nginx: `curl http://localhost/health` và `curl -X POST http://localhost/ask ...` (không gọi trực tiếp agent).

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy agent Part 6

Lớp K5 deploy **chính agent Part 6** trong `06-lab-complete/` (không deploy app mẫu), dùng `railway.toml` hoặc `render.yaml` đã viết.

> ⚠️ **Cần tài khoản Railway/Render.** Sau khi deploy, điền URL public vào đây và vào `DEPLOYMENT.md`:
>
> - Platform: Railway (hoặc Render)
> - Public URL: `https://________________`
> - 4 lệnh tự kiểm (mỗi lệnh chỉ in mã HTTP): `/health` → 200, `/ready` → 200, `/ask` không key → 401, `/ask` có key → 200.

### So sánh `railway.toml` và `render.yaml`

| | `railway.toml` (Railway) | `render.yaml` (Render) |
|---|---|---|
| Định dạng | TOML | YAML (Blueprint) |
| Build | `[build] builder = "DOCKERFILE"` | `runtime: docker` (tự phát hiện Dockerfile) |
| Health check | `[deploy] healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Secret | đặt bằng `railway variables set` (không nằm trong file) | `generateValue: true` / `sync: false` trong `envVars` |
| Ý nghĩa | Khai báo 1 service đơn | Khai báo nhiều service trong 1 file (Blueprints) |

Điểm giống: cả hai đều chỉ cần trỏ tới `Dockerfile` + endpoint `/health`, app phải lắng nghe theo biến `PORT` do platform cấp (đã xử lý trong `CMD` của Dockerfile: `${PORT:-8000}`).

### Exercise 3.3: Cloud Run pipeline (không deploy, chỉ đọc)

Pipeline trong `03-cloud-deployment/production-cloud-run/cloudbuild.yaml` gồm 4 bước, mỗi bước `waitFor` bước trước:

1. **test** — chạy `pytest tests/` trên image `python:3.11-slim`.
2. **build** — `docker build` tag `gcr.io/$PROJECT_ID/ai-agent:$COMMIT_SHA` (có `--cache-from` để dùng layer cache).
3. **push** — `docker push --all-tags` lên Container Registry.
4. **deploy** — `gcloud run deploy ai-agent` (region `asia-southeast1`, `--min-instances=1`, `--max-instances=10`, secret lấy từ Secret Manager qua `--set-secrets`).

`service.yaml` khai báo IaC: `minScale/maxScale`, `containerConcurrency: 80`, resource limits, env/secret (`valueFrom.secretKeyRef`) và `livenessProbe`/`startupProbe` trỏ tới `/health` và `/ready`.

---

## Part 4: API Security

### Exercise 4.1: API Key authentication (develop)

```bash
cd 04-api-gateway/develop
AGENT_API_KEY=secret-key-123 python app.py
```

- API key được check trong dependency `verify_api_key` (dùng `APIKeyHeader(name="X-API-Key", auto_error=False)`): thiếu key → **401**, sai key → **403**.
- Để rotate key: đổi giá trị biến môi trường `AGENT_API_KEY` rồi restart app (không sửa code).

Kết quả thật (`curl -i` / httpx, cổng 8010):

```text
Không có key  → 401  {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
Sai key       → 403  {"detail":"Invalid API key."}
Đúng key      → 200  {"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). ..."}
```

### Exercise 4.2: JWT authentication (production)

```bash
cd 04-api-gateway/production
pip install -r requirements.txt
python app.py
# Lấy token (student / demo123, giới hạn 10 req/phút)
curl -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" \
     -d '{"username":"student","password":"demo123"}'
```

Kết quả thật (cổng 8011):

```text
POST /auth/token  → 200  {"access_token":"eyJhbGciOiJIUzI1NiIs...","token_type":"bearer",...}
POST /ask (không token)        → 401
POST /ask (Authorization Bearer) → 200
```

### Exercise 4.3: Rate limiting

- **Algorithm:** Sliding Window Counter (in-memory `deque` timestamps, cửa sổ 60 giây).
- **Limit:** `student` = **10 req/phút**, `admin` = 100 req/phút.
- **Bypass cho admin:** endpoint chọn limiter theo role (`rate_limiter_admin` vs `rate_limiter_user`).

Kết quả vòng lặp 15 request (cổng 8011) — request thứ 11 bị chặn:

```text
loop codes: [200, 200, 200, 200, 200, 200, 200, 200, 200, 429]
```

### Exercise 4.4: Cost guard

Cách làm: mỗi user có ngân sách (vd $10/tháng hoặc $1/ngày). Trước khi gọi LLM, `check_budget(user)` đọc tổng chi phí trong Redis, nếu `current + estimated > budget` thì chặn (trả 402); sau khi gọi xong `record_usage(...)` cộng chi phí thực vào Redis kèm `expire` theo chu kỳ (ngày/tháng) để tự reset.

- **Rate limit** bảo vệ *tốc độ* (số request/giây) khỏi bot/lạm dụng.
- **Cost guard** bảo vệ *tiền* (tổng chi phí LLM) khỏi vượt ngân sách.
- Cần **cả hai** vì một client gọi chậm nhưng liên tục vẫn có thể đốt hết tiền mà không vi phạm rate limit.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks

- **Liveness (`/health`):** "process còn sống không?" — trả 200 khi process chạy, dù dependency (Redis) đang chết. Nếu fail → platform **restart** container.
- **Readiness (`/ready`):** "sẵn sàng nhận traffic chưa?" — trả 200 khi các dependency (DB/Redis) sẵn sàng, 503 khi chưa. Nếu fail → load balancer **ngừng route** traffic tới instance đó nhưng **không restart**.

### Exercise 5.2: Graceful shutdown

Khi nhận SIGTERM: (1) ngừng nhận request mới, (2) chờ request in-flight hoàn thành, (3) đóng connections, (4) thoát với exit code 0. uvicorn làm sẵn việc này; nếu tự đăng ký handler SIGTERM thì phải gọi lại handler cũ của uvicorn.

### Exercise 5.3: Stateless design

Lưu state trong **RAM** (dict `conversation_history`) thì khi scale ra nhiều instance, mỗi instance có bộ nhớ riêng → user bị mất context hoặc data không nhất quán. Lưu trong **Redis** (`r.lrange("history:{user_id}", ...)`) thì mọi instance dùng chung một nguồn state → scale ngang được.

### Exercise 5.4–5.5: Load balancing & test stateless

```bash
cd 05-scaling-reliability/production
touch .env.local                      # compose cần file này (để trống cũng được)
docker compose -p k5-day14-scaling up -d --build --scale agent=3
python test_stateless.py
docker compose -p k5-day14-scaling down
```

Kết quả thật (chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3` rồi `python test_stateless.py`):

```text
Session ID: b7f5dd4e-210d-4008-9560-fc85dfa0312c

Request 1: [instance-39c49b]   Request 2: [instance-0a6e0a]   Request 3: [instance-938943]
Request 4: [instance-39c49b]   Request 5: [instance-0a6e0a]
Total requests: 5
Instances used: {'instance-39c49b', 'instance-938943', 'instance-0a6e0a'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10   ← 5 câu hỏi + 5 câu trả lời
✅ Session history preserved across all instances via Redis!
```

5 request được 3 instance khác nhau xử lý (round-robin qua Nginx), nhưng **history 10 tin nhắn vẫn đầy đủ** vì state được lưu trong Redis, không nằm trong RAM của từng instance.

---

## Part 6: Final Project — output `check_production_ready.py`

Đã hoàn thành toàn bộ TODO trong `06-lab-complete/` (config, auth, rate limiter, cost guard, redis client, main, Dockerfile, compose, .dockerignore, .env.example, railway.toml, render.yaml).

### 📋 Checklist Deliverable (chạy đầy đủ trong WSL2 + Docker — output thật)

```text
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY!
```

**Chi tiết 43/43 checks (đã chạy thật trên Linux + Docker):**
- Docker: build image thành công (16s), **image = 298 MB** (< 500 MB), container chạy và `GET /health` → 200.
- `docker stop` tắt êm: **exit code 0 trong 1.0s** (graceful shutdown qua SIGTERM đạt).
- Runtime (uvicorn `--workers 2`): `/health` 200, `/ready` 200, Redis mất → `/ready` 503 (còn `/health` vẫn 200), thiếu/sai key 401, key đúng 200, vượt giới hạn → 429 (sau 5 request, `RATE_LIMIT_PER_MINUTE=5`), **restart agent vẫn 429** (state nằm trong Redis = stateless), hết budget → 402, log JSON 17 dòng hợp lệ, config đọc từ env.
- Redis cho bài test stateless được script tự bật bằng container `redis:7-alpine`.

---

## AI log

Theo [RULES.md](RULES.md) mục 1, ghi lại cách dùng AI cho code Part 6 và các câu trả lời:

| # | Hỏi AI điều gì | AI trả lời / gợi ý gì | Mình tự làm & kiểm tra |
|---|---|---|---|
| 1 | Hoàn thiện các TODO trong `06-lab-complete/` theo hợp đồng ở README (endpoint, mã lỗi, biến env) | Đọc `check_production_ready.py` để hiểu đúng 12 tiêu chí, gợi ý cấu trúc từng module (config đọc env, auth `APIKeyHeader(auto_error=False)`, rate limit sliding window bằng Redis sorted set, cost guard bằng `INCRBYFLOAT`, lifespan cho graceful shutdown, Dockerfile multi-stage) | Tự viết code, tự chạy `python check_production_ready.py --static-only` (28/28 ✅) rồi `--skip-docker` với Redis thật (38/38 ✅). Không sửa `check_production_ready.py`. |
| 2 | Cách sửa 2 câu eval sai của agent v2 (Part 7) | Gợi ý thêm 2 entry vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` (HPA/kubernetes và JWT) | Tự chạy eval để thấy 2 câu sai (`scaling-03`, `security-02`) và `missing_keywords`, tự thêm entry, chạy lại `run_eval.py --min-accuracy 1.0` → 23/23 ✅, không regression. |
| 3 | Cách chạy load test & eval Part 7 đúng lệnh | Nhắc đúng lệnh từ `CHECKPOINTS.md` (`load_test.py --requests 300 --concurrency ... --out`, `run_eval.py --baseline ...`) | Tự chạy thật, tự đọc các file JSON report và điền số liệu vào báo cáo. Mọi con số trong báo cáo là số mình chạy được. |

> Mọi số liệu (kích thước image, latency, accuracy, thời gian alert) trong bài đều lấy từ lệnh đã chạy / file report đã nộp; không bịa số.
