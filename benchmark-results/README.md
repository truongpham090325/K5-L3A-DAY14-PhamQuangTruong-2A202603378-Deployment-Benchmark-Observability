# benchmark-results/

Thư mục này chứa CSV kết quả Locust headless (Part 7 Bước 2 — cần Docker).

Sau khi bật stack observability (`docker compose -p k5-day14-observability up -d --build`), chạy:

```bash
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1
docker compose -p k5-day14-observability up -d --scale agent=3
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
```

File cần có ở đây:
- `scale_1_stats.csv`
- `scale_3_stats.csv`
