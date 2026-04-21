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

echo "[1/5] Check bionicpro-auth health"
retry_curl http://localhost:8000/healthz
curl -fsS http://localhost:8000/healthz
echo

echo "[2/5] Check report-api health"
retry_curl http://localhost:8001/healthz
curl -fsS http://localhost:8001/healthz
echo

echo "[3/5] Check frontend availability"
retry_curl http://localhost:3000
curl -fsS http://localhost:3000 >/dev/null
echo "frontend: ok"

echo "[4/5] Check keycloak availability"
retry_curl http://localhost:8080/realms/reports-realm/.well-known/openid-configuration 40 2
curl -fsS http://localhost:8080/realms/reports-realm/.well-known/openid-configuration >/dev/null
echo "keycloak realm: ok"

echo "[5/7] Check profile-api health"
retry_curl http://localhost:8002/healthz
curl -fsS http://localhost:8002/healthz
echo
echo "profile-api: ok"

echo "[6/7] Check ClickHouse HTTP"
retry_curl http://localhost:8123/ping 30 2
curl -fsS http://localhost:8123/ping
echo
echo "clickhouse: ok"

echo "[7/7] Check Airflow webserver (может подниматься дольше остальных)"
retry_curl http://localhost:8088/health 60 3
curl -fsS http://localhost:8088/health
echo
echo "airflow: ok"

echo "Smoke check passed."
