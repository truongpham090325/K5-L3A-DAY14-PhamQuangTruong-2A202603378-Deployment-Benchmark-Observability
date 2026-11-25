# Benchmark & Observability Report — Day 14

**Họ tên:** Phạm Quang Trường
**MSSV:** 2A202603378
**Ngày chạy:** 25/11/2026
**Môi trường:** Windows 10, Python 3.13 (agent chạy local cho Bước 1; Bước 2 chạy Docker Compose trên máy có Docker Desktop — WSL2)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Mock LLM base ~120ms + jitter; 500ms đủ thoải mái cho UX nhưng bắt được tail latency bất thường |
| Error rate `/ask` | < 2 % | LLM upstream có ~1% lỗi ngẫu nhiên; 2% chừa error budget hợp lý |
| Accuracy trên golden dataset | ≥ 80 % | Chặn deploy khi chất lượng tụt rõ rệt; bản fixed đạt 100% |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.0 | 203.5 | 234.8 | 1712.4 | 0.67% | ✅ |
| 10 | 37.81 | 202.5 | 445.0 | 1698.3 | 1.33% | ✅ |
| 50 | 92.56 | 209.8 | 531.0 | 1726.1 | 0.00% | ❌ (p95) |
| 100 | 49.0 | 682.5 | 3821.6 | 4196.8 | 1.00% | ❌ (p95) |

**Nhận xét:** RPS **không** tăng tuyến tính theo concurrency: tăng từ 4 → 37.8 → 92.6 khi lên 1 → 10 → 50, nhưng **tụt xuống 49** ở concurrency 100. Nguyên nhân: agent develop chạy **1 uvicorn worker duy nhất** (`uvicorn.run(app)` không có `--workers`), nên khi 100 request đổ vào cùng lúc, event loop bị bão hoà (mock LLM có phần CPU-bound + GIL), queue dài làm latency tăng vọt (p95 3821ms) và throughput giảm. Điểm nghẽn nằm ở **CPU/worker của chính app**, không phải LLM.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 218.6 | 474.2 | 502.7 |
| 0.03 (mặc định) | 269.9 | 488.9 | 1756.9 |
| 0.1 | 371.3 | 1706.6 | 1973.3 |

**Nhận xét:** Chỉ số nhạy nhất với request chậm là **p99** (502 → 1973 ms) rồi tới p95 (474 → 1706 ms), trong khi **avg chỉ nhúc nhích** (218 → 371 ms). Đúng như lý thuyết: chỉ ~3–10% request chậm bị "pha loãng" trong trung bình cộng. Vì vậy SLO phải đặt theo **p95/p99** để nắm được trải nghiệm của người dùng "kém may mắn", không đặt theo average.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.8 | 109.0 | 113.7 |
| Tổng cost (USD) | $0.000400 | $0.000760 | $0.000790 |
| Cost / câu đúng (USD) | $0.00040035 | $0.00003619 | $0.00003436 |
| Quality gate | FAIL | PASS | PASS (≥ 100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["hpa","kubernetes","autoscal"], "...CPU, memory hoặc custom metrics...")` vào `KNOWLEDGE_BASE` |
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt"], "...JWT là token có chữ ký số... thời điểm hết hạn...")` vào `KNOWLEDGE_BASE` |

**Trade-off chất lượng / chi phí / latency giữa v1 và v2:** v2 (có retrieval/RAG) chính xác hơn hẳn (4.3% → 91.3%) nhưng tốn gấp đôi token mỗi câu (56.8 → 109.0) và tổng cost gần gấp đôi ($0.0004 → $0.00076). Nhưng tính theo **cost / câu trả lời đúng** thì v2 **rẻ hơn ~10 lần** ($0.00003619 so với $0.00040035) vì v1 trả lời sai gần như toàn bộ. Đây chính là lý do "cost / câu đúng" tốt hơn "cost / câu" khi so sánh hai phiên bản.

---

## 4. Observability stack (production)

> ⚠️ **Phần này cần Docker Desktop + WSL2.** Các lệnh bên dưới dùng `-p k5-day14-observability` để tránh trùng tên project với `02-docker`/`05-scaling-reliability`.

```bash
cd 06-lab-complete/benchmark-observability/production
docker compose -p k5-day14-observability up -d --build --scale agent=1
# Grafana :3000 · Prometheus :9090 · Jaeger :16686 · Locust :8089 · Agent qua Nginx :8080
```

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) → `screenshots/grafana-dashboard.png`
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) → `screenshots/jaeger-slow-trace.png`
- [ ] Một trace lỗi trong Jaeger (có event `exception`) → `screenshots/jaeger-error-trace.png`
- [ ] Trang Alerts của Prometheus với ≥ 2 alert đang **firing** → `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~1 phút | Error rate |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~2 phút | p95 latency |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | — | Cost USD/giờ |
| D | `docker pause` 1 instance | `AgentInstanceDown` | — | Instances up |
| E | `AGENT_VERSION=v1` | (không có) | — | Retrieval hit ratio / version |

**Thí nghiệm E không làm alert nào firing. Phát hiện loại sự cố này bằng cách nào?** Đổi `AGENT_VERSION=v1` làm **chất lượng câu trả lời** giảm mạnh, nhưng metric hạ tầng (latency, error rate, cost) vẫn xanh vì agent vẫn "chạy nhanh và không lỗi". Loại sự cố *chất lượng* này chỉ bắt được bằng **eval định kỳ / quality gate trong CI** (golden dataset + `run_eval.py --min-accuracy`), hoặc LLM-as-judge trên traffic thật — không phải bằng alert hạ tầng.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được:

- `trace_id`: `________________`
- Tổng thời gian: ______ ms
- Span chiếm nhiều thời gian nhất: ______ (______ ms, ______%)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"event": "llm_error", "trace_id": "________________", ...}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

```bash
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1
docker compose -p k5-day14-observability up -d --scale agent=3
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
```

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** (điền sau khi chạy — nếu scale lên 3 mà p95 gần như không đổi, nút thắt nằm ở **latency LLM** chứ không phải số instance; xem panel LLM latency.)

---

## 6. Kết luận

**3 điều học được về benchmark & observability:**

1. **Percentile quan trọng hơn trung bình.** avg chỉ tăng nhẹ trong khi p99 tăng vọt khi có tail latency → SLO phải đặt theo p95/p99 để phản ánh trải nghiệm thật của người dùng.
2. **"Cost / câu đúng" tốt hơn "cost / câu".** v2 tốn token gấp đôi nhưng rẻ hơn ~10 lần trên mỗi câu trả lời đúng — benchmark giúp định lượng trade-off chất lượng/chi phí.
3. **Observability hạ tầng không bắt được lỗi chất lượng.** Đổi sang agent v1 (trả lời sai) thì không alert nào firing — cần eval/quality gate trong CI để chặn regression về chất lượng, song song với metrics/traces/alerts cho hiệu năng.

**Nếu đưa lên production thật, sẽ thêm metric / alert:** alert cho **token cost đốt nhanh bất thường** (burn rate), **tỉ lệ retrieval miss** (hit ratio thấp), **synthetic check từ ngoài** (vì lỗi 504 ở Nginx không hiện trong metric của agent), và **sampling trace** để kiểm soát chi phí khi traffic lớn.

---

## File bằng chứng

- `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`
- `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`
- `reports/eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`
- `benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv` (Locust headless)
- `screenshots/grafana-dashboard.png`, `jaeger-slow-trace.png`, `jaeger-error-trace.png`, `prometheus-alert-firing.png`
