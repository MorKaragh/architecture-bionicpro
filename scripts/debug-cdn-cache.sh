#!/usr/bin/env bash
# Два GET подряд к CDN (:8090) на один и тот же объект — первый MISS, второй HIT (если proxy_cache пишется).
# Пример: ./scripts/debug-cdn-cache.sh 'reports/prothetic1/2026-05-01T00-00-07.418000.json'
set -euo pipefail
cd "$(dirname "$0")/.."

KEY="${1:-}"
if [ -z "$KEY" ]; then
  echo "usage: $0 <object-key-under-bucket>" >&2
  echo "  example: $0 'reports/prothetic1/2026-05-01T00-00-07.418000.json'" >&2
  exit 1
fi

echo "== 1) Очистка файлов proxy_cache в контейнере cdn (только для проверки) =="
docker compose exec -T cdn sh -c 'rm -rf /var/cache/nginx/report_cache/* 2>/dev/null || true'

URL_PATH="/reports-cache/${KEY#/}"
echo "== 2) Два запроса к http://localhost:8090${URL_PATH} =="
echo "--- запрос A ---"
curl -sS -D- -o /dev/null -H 'Accept-Encoding: identity' "http://localhost:8090${URL_PATH}" | tr -d '\r' | grep -iE '^(HTTP/|x-cache-status:)'
echo "--- запрос B (тот же URL) ---"
curl -sS -D- -o /dev/null -H 'Accept-Encoding: identity' "http://localhost:8090${URL_PATH}" | tr -d '\r' | grep -iE '^(HTTP/|x-cache-status:)'

echo "== 3) Хвост лога cdn (должны быть две строки с upstream_cache=MISS и HIT) =="
docker compose logs cdn --tail 8 2>&1 | tail -8
