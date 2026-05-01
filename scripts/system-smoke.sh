#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

retry() {
  local attempts="$1"
  local sleep_seconds="$2"
  shift 2
  local i
  for i in $(seq 1 "$attempts"); do
    if "$@"; then
      return 0
    fi
    sleep "$sleep_seconds"
  done
  return 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd curl
require_cmd python3
require_cmd docker

echo "[1/5] Базовая проверка доступности сервисов"
./scripts/task1-smoke.sh

echo "[2/5] Проверка CDC-пайплайна"
./scripts/task4-cdc-smoke.sh

echo "[3/5] Получение access token для проверки report-api"
retry 30 2 curl -fsS http://localhost:8080/realms/reports-realm/.well-known/openid-configuration >/dev/null

admin_token="$(curl -fsS \
  -X POST "http://localhost:8080/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=password" \
  --data-urlencode "client_id=admin-cli" \
  --data-urlencode "username=admin" \
  --data-urlencode "password=admin" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"

prothetic_user_id="$(curl -fsS \
  "http://localhost:8080/admin/realms/reports-realm/users?username=prothetic1" \
  -H "Authorization: Bearer ${admin_token}" \
  | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data[0]["id"] if data else "")')"

if [ -z "${prothetic_user_id}" ]; then
  echo "Cannot find Keycloak user prothetic1 in reports-realm." >&2
  exit 1
fi

# В тестовом окружении у пользователя может быть required action CONFIGURE_TOTP,
# что блокирует password grant; снимаем для автоматизированной проверки.
curl -fsS -X PUT \
  "http://localhost:8080/admin/realms/reports-realm/users/${prothetic_user_id}" \
  -H "Authorization: Bearer ${admin_token}" \
  -H "Content-Type: application/json" \
  -d '{"requiredActions":[]}' >/dev/null

report_token="$(curl -fsS \
  -X POST "http://localhost:8080/realms/reports-realm/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=password" \
  --data-urlencode "client_id=admin-cli" \
  --data-urlencode "username=prothetic1" \
  --data-urlencode "password=prothetic123" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"

echo "[4/5] Проверка формирования отчёта в report-api"
report_json="$(curl -fsS \
  "http://localhost:8001/reports" \
  -H "Authorization: Bearer ${report_token}")"

report_status="$(printf '%s' "${report_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("report_status",""))')"
report_url="$(printf '%s' "${report_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("report_url",""))')"
report_owner="$(printf '%s' "${report_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("report_owner",""))')"

if [ "${report_status}" != "ready" ]; then
  echo "Expected report_status=ready, got '${report_status}'." >&2
  echo "${report_json}" >&2
  exit 1
fi

if [ -z "${report_url}" ] || [ -z "${report_owner}" ]; then
  echo "Report response does not include report_url/report_owner." >&2
  echo "${report_json}" >&2
  exit 1
fi
echo "report-api: ready for user ${report_owner}"

echo "[5/5] Проверка CDN отдачи отчёта и cache HIT"
object_path="${report_url#*\/reports-cache/}"
cdn_url="http://localhost:8090/reports-cache/${object_path}"

first_headers="$(curl -fsS -D - -o /dev/null "${cdn_url}")"
second_headers="$(curl -fsS -D - -o /dev/null "${cdn_url}")"
second_cache_status="$(printf '%s' "${second_headers}" | python3 -c 'import re,sys; h=sys.stdin.read(); m=re.search(r"(?im)^x-cache-status:\\s*([^\\r\\n]+)", h); print(m.group(1).strip() if m else "")')"

if [ "${second_cache_status}" != "HIT" ]; then
  echo "Expected CDN second request X-Cache-Status=HIT, got '${second_cache_status}'." >&2
  echo "First response headers:" >&2
  echo "${first_headers}" >&2
  echo "Second response headers:" >&2
  echo "${second_headers}" >&2
  exit 1
fi

echo "System smoke passed: health, CDC, reports, CDN cache."
