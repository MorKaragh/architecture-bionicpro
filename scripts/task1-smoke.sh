#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

retry_curl() {
  local url="$1"
  local attempts="${2:-20}"
  local sleep_seconds="${3:-2}"

  for ((i=1; i<=attempts; i++)); do
    if curl -fsS "$url" >/dev/null; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "Failed to reach $url after $attempts attempts" >&2
  return 1
}

echo "[1/9] Check bionicpro-auth health"
retry_curl http://localhost:8000/healthz
curl -fsS http://localhost:8000/healthz
echo

echo "[2/9] Check report-api health"
retry_curl http://localhost:8001/healthz
curl -fsS http://localhost:8001/healthz
echo

echo "[3/9] Check frontend availability"
retry_curl http://localhost:3000
curl -fsS http://localhost:3000 >/dev/null
echo "frontend: ok"

echo "[4/9] Check keycloak availability"
retry_curl http://localhost:8080/realms/reports-realm/.well-known/openid-configuration 40 2
curl -fsS http://localhost:8080/realms/reports-realm/.well-known/openid-configuration >/dev/null
echo "keycloak realm: ok"

echo "[5/9] Check profile-api health"
retry_curl http://localhost:8002/healthz
curl -fsS http://localhost:8002/healthz
echo
echo "profile-api: ok"

echo "[6/9] Check ClickHouse HTTP"
retry_curl http://localhost:8123/ping 30 2
curl -fsS http://localhost:8123/ping
echo
echo "clickhouse: ok"

echo "[7/9] Check Airflow webserver (может подниматься дольше остальных)"
retry_curl http://localhost:8088/health 60 3
curl -fsS http://localhost:8088/health
echo
echo "airflow: ok"

echo "[8/9] Check MinIO health"
retry_curl http://localhost:9005/minio/health/live 30 2
curl -fsS http://localhost:9005/minio/health/live
echo
echo "minio: ok"

echo "[9/9] Check CDN nginx (эмуляция CDN для отчётов)"
curl -sI http://localhost:8090/reports-cache/ | head -n 1 | grep -q "HTTP" || {
  echo "cdn nginx: no HTTP response on :8090" >&2
  exit 1
}
echo "cdn nginx: listening"

echo "Smoke check passed."
