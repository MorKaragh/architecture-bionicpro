#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/4] Проверка Kafka Connect"
curl -fsS http://localhost:8083/connectors/crm-connector/status >/dev/null
echo "kafka-connect: crm-connector status ok"

if ! curl -fsS 'http://localhost:8123/?user=reports&password=reports_password' \
  --data-binary "EXISTS TABLE reports.user_report_mart_cdc FORMAT TabSeparatedRaw" | grep -q "^1$"; then
  echo "missing table reports.user_report_mart_cdc in ClickHouse." >&2
  echo "apply migration manually: docker compose exec -T clickhouse clickhouse-client --user reports --password reports_password --queries-file /docker-entrypoint-initdb.d/002_cdc_pipeline.sql" >&2
  exit 1
fi

echo "[2/4] Обновление CRM-сегмента для user1 (источник CDC)"
docker compose exec -T sources_db psql -U sources_user -d sources_db -c \
  "UPDATE crm.clients SET segment = 'vip' WHERE user_key = 'user1';" >/dev/null
echo "crm.clients updated"

echo "[3/4] Ожидание доставки изменения в ClickHouse витрину"
for i in $(seq 1 25); do
  segment="$(curl -fsS 'http://localhost:8123/?user=reports&password=reports_password' \
    --data-binary "SELECT crm_segment FROM reports.user_report_mart_cdc WHERE user_key='user1' ORDER BY data_as_of DESC LIMIT 1 FORMAT TabSeparatedRaw" || true)"
  if [ "$segment" = "vip" ]; then
    echo "cdc delivery: ok"
    break
  fi
  sleep 2
done

segment="$(curl -fsS 'http://localhost:8123/?user=reports&password=reports_password' \
  --data-binary "SELECT crm_segment FROM reports.user_report_mart_cdc WHERE user_key='user1' ORDER BY data_as_of DESC LIMIT 1 FORMAT TabSeparatedRaw")"
if [ "$segment" != "vip" ]; then
  echo "cdc delivery failed: expected vip, got '$segment'" >&2
  exit 1
fi

echo "[4/4] Проверка API-таблицы cdc-витрины"
table_name="$(docker compose exec -T report-api /bin/sh -c 'echo "$CLICKHOUSE_REPORT_TABLE"')"
if [ "$table_name" != "reports.user_report_mart_cdc" ]; then
  echo "report-api configured with unexpected table: $table_name" >&2
  exit 1
fi
echo "report-api table: $table_name"

echo "Task4 CDC smoke passed."
