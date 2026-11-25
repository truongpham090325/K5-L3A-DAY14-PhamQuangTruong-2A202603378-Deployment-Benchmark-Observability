# Deployment Information

## Public URL

> ⚠️ **Điền sau khi deploy lên Render** (xem các bước bên dưới). Render Blueprint đọc `06-lab-complete/render.yaml`.

```
https://your-agent.onrender.com
```

## Platform

Render (Blueprint — `render.yaml`)

## Cách deploy (Render)

`render.yaml` nằm trong `06-lab-complete/`, đã khai báo:
- **web service** `production-agent`: `runtime: docker`, `healthCheckPath: /health`, `AGENT_API_KEY` dùng `generateValue: true` (Render tự sinh, không ghi thẳng).
- **redis service** `agent-redis`: `type: redis`, plan free; `REDIS_URL` được nối vào web service qua `fromService`.

Các bước:

1. Push repo lên GitHub (public).
2. Render Dashboard → **New → Blueprint** → chọn repo.
3. Render đọc `render.yaml` (nếu cần, chỉ đường dẫn tới thư mục `06-lab-complete/` hoặc để file ở root).
4. Review rồi **Apply**. Render tự build Docker image và provision Redis.
5. Lấy public URL (`https://production-agent.onrender.com` hoặc tương tự).
6. Chờ `/ready` trả 200 (agent đã kết nối Redis) trước khi chụp ảnh.

> Nếu Render không tự nhận Redis qua `fromService`, mở tab **Environment** của web service, đặt `REDIS_URL` bằng connection string của Redis instance (dạng `rediss://...`) — đặt trên dashboard, **không ghi vào code**.

## Test Commands

Thay `BASE` bằng URL public của bạn:

```bash
BASE="https://your-agent.onrender.com"
AGENT_API_KEY="<key Render đã tự sinh — xem tab Environment>"

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'    # 401 (thiếu key)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'                                    # 200
```

## Environment Variables Set

Trên Render (qua `render.yaml` / dashboard, KHÔNG ghi trong code):

- `PORT` — do platform cấp (Dockerfile dùng `${PORT:-8000}`)
- `REDIS_URL` — connection string tới Redis managed (để `/ready` trả 200)
- `AGENT_API_KEY` — `generateValue: true` (Render tự sinh)
- `RATE_LIMIT_PER_MINUTE` — `10`
- `DAILY_BUDGET_USD` — `1.0`
- `ENVIRONMENT` — `production`

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)

> Chụp 3 ảnh trên sau khi deploy xong và lưu vào `screenshots/`. 4 lệnh tự kiểm ở CP6 (in mã HTTP, không lộ key) chính là 4 lệnh ở mục "Test Commands" trên.
