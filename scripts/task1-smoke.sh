#!/usr/bin/env bash
set -euo pipefail

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

echo "[5/5] Check profile-api health"
retry_curl http://localhost:8002/healthz
curl -fsS http://localhost:8002/healthz
echo
echo "profile-api: ok"

echo "Smoke check passed."
