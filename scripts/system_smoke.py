#!/usr/bin/env python3
import json
import subprocess
import sys
import time
import base64
import urllib.error
import urllib.parse
import urllib.request

SMOKE_USERNAME = "smoke_user"
SMOKE_PASSWORD = "smoke_user_123"


def log(step: str, message: str) -> None:
    print(f"[{step}] {message}")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, str], str]:
    req = urllib.request.Request(url, method=method, data=data)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp_headers, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        resp_headers = {k.lower(): v for k, v in e.headers.items()}
        return e.code, resp_headers, body


def wait_http_ok(url: str, attempts: int = 30, sleep_s: float = 2.0) -> None:
    for _ in range(attempts):
        status, _, _ = http_request("GET", url, timeout=5.0)
        if 200 <= status < 300:
            return
        time.sleep(sleep_s)
    fail(f"Service is not ready: {url}")


def ensure_health(url: str, title: str) -> None:
    wait_http_ok(url)
    status, _, body = http_request("GET", url, timeout=5.0)
    if not (200 <= status < 300):
        fail(f"{title} healthcheck failed, status={status}, body={body}")
    log("health", f"{title}: ok")


def post_form(url: str, fields: dict[str, str], headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], str]:
    payload = urllib.parse.urlencode(fields).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    if headers:
        hdrs.update(headers)
    return http_request("POST", url, headers=hdrs, data=payload, timeout=15.0)


def get_admin_token() -> str:
    status, _, body = post_form(
        "http://localhost:8080/realms/master/protocol/openid-connect/token",
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "admin",
            "password": "admin",
        },
    )
    if status != 200:
        fail(f"Cannot get Keycloak admin token: status={status}, body={body}")
    return json.loads(body)["access_token"]


def keycloak_find_user_id(token: str, username: str) -> str:
    url = f"http://localhost:8080/admin/realms/reports-realm/users?username={urllib.parse.quote(username)}"
    status, _, body = http_request("GET", url, headers={"Authorization": f"Bearer {token}"}, timeout=15.0)
    if status != 200:
        fail(f"Cannot query Keycloak user {username}: status={status}, body={body}")
    users = json.loads(body)
    if not users:
        fail(f"User not found in Keycloak: {username}")
    return users[0]["id"]


def keycloak_clear_required_actions(token: str, user_id: str) -> None:
    status, _, body = http_request(
        "PUT",
        f"http://localhost:8080/admin/realms/reports-realm/users/{user_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps({"requiredActions": []}).encode("utf-8"),
        timeout=15.0,
    )
    if status not in (200, 204):
        fail(f"Cannot clear requiredActions for user {user_id}: status={status}, body={body}")


def keycloak_set_password(token: str, user_id: str, password: str) -> None:
    status, _, body = http_request(
        "PUT",
        f"http://localhost:8080/admin/realms/reports-realm/users/{user_id}/reset-password",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "type": "password",
                "temporary": False,
                "value": password,
            }
        ).encode("utf-8"),
        timeout=15.0,
    )
    if status not in (200, 204):
        fail(f"Cannot reset password for user {user_id}: status={status}, body={body}")


def keycloak_ensure_user(token: str, username: str) -> str:
    status, _, body = http_request(
        "POST",
        "http://localhost:8080/admin/realms/reports-realm/users",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "username": username,
                "enabled": True,
                "emailVerified": True,
                "requiredActions": [],
            }
        ).encode("utf-8"),
        timeout=15.0,
    )
    if status not in (201, 409):
        fail(f"Cannot create/ensure user {username}: status={status}, body={body}")
    return keycloak_find_user_id(token, username)


def ensure_smoke_user_data() -> None:
    # Гарантируем строку для smoke_user напрямую, чтобы smoke не зависел
    # от наличия user1/prothetic1 в витрине.
    query = """
    INSERT INTO reports.user_report_mart_cdc
      (user_key, prosthesis_uptime_hours, training_sessions, battery_cycles, crm_segment, data_as_of)
    VALUES
      ('smoke_user', 7.0, 2, 3, 'smoke', now())
    """
    clickhouse_query(query)


def get_report_token(username: str, password: str) -> str:
    status, _, body = post_form(
        "http://localhost:8080/realms/reports-realm/protocol/openid-connect/token",
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": username,
            "password": password,
            "scope": "openid profile email",
        },
    )
    if status != 200:
        fail(f"Cannot get report token for {username}: status={status}, body={body}")
    token_response = json.loads(body)

    def jwt_payload(token: str) -> dict:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        try:
            return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
        except Exception:
            return {}

    # В этом контуре access token admin-cli "облегченный" и без preferred_username.
    # Для report-api выбираем токен, где есть user identifier.
    candidates = [
        token_response.get("id_token"),
        token_response.get("access_token"),
    ]
    for token in candidates:
        if not token:
            continue
        payload = jwt_payload(token)
        if payload.get("preferred_username") or payload.get("username"):
            return token

    fail(
        "Cannot get token with user identifier for prothetic1; "
        "both id_token/access_token miss preferred_username/username"
    )


def docker_compose_exec(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", *args],
        capture_output=True,
        text=True,
    )


def clickhouse_query(query: str) -> str:
    status, _, body = http_request(
        "POST",
        "http://localhost:8123/?user=reports&password=reports_password",
        data=query.encode("utf-8"),
        timeout=20.0,
    )
    if status != 200:
        fail(f"ClickHouse query failed: status={status}, query={query}, body={body}")
    return body.strip()


def run_cdc_check() -> None:
    probe = subprocess.run(["docker", "compose", "ps"], capture_output=True, text=True)
    if probe.returncode != 0:
        fail(
            "docker compose недоступен из текущего окружения. "
            "Проверьте, что Docker Desktop запущен и команда `docker compose ps` работает."
        )

    exists = clickhouse_query("EXISTS TABLE reports.user_report_mart_cdc FORMAT TabSeparatedRaw")
    if exists != "1":
        fail("Missing ClickHouse table reports.user_report_mart_cdc")

    update = docker_compose_exec(
        [
            "sources_db",
            "psql",
            "-U",
            "sources_user",
            "-d",
            "sources_db",
            "-c",
            "UPDATE crm.clients SET segment = 'vip' WHERE user_key = 'user1';",
        ]
    )
    if update.returncode != 0:
        fail(f"Cannot update sources_db for CDC check:\n{update.stdout}\n{update.stderr}")

    for _ in range(25):
        segment = clickhouse_query(
            "SELECT crm_segment FROM reports.user_report_mart_cdc "
            "WHERE user_key='user1' ORDER BY data_as_of DESC LIMIT 1 FORMAT TabSeparatedRaw"
        )
        if segment == "vip":
            break
        time.sleep(2)
    else:
        fail("CDC delivery failed: crm_segment for user1 did not become 'vip'")

    table_name_proc = docker_compose_exec(
        [
            "report-api",
            "/bin/sh",
            "-c",
            "echo \"$CLICKHOUSE_REPORT_TABLE\"",
        ]
    )
    if table_name_proc.returncode != 0:
        fail(f"Cannot read CLICKHOUSE_REPORT_TABLE from report-api:\n{table_name_proc.stderr}")
    table_name = table_name_proc.stdout.strip()
    if table_name != "reports.user_report_mart_cdc":
        fail(f"report-api configured with unexpected table: {table_name}")


def run() -> None:
    log("1/5", "Проверка health ключевых сервисов")
    ensure_health("http://localhost:8000/healthz", "bionicpro-auth")
    ensure_health("http://localhost:8001/healthz", "report-api")
    ensure_health("http://localhost:8002/healthz", "profile-api")
    ensure_health("http://localhost:3000", "frontend")
    ensure_health("http://localhost:8080/realms/reports-realm/.well-known/openid-configuration", "keycloak")
    ensure_health("http://localhost:8123/ping", "clickhouse")
    ensure_health("http://localhost:8088/health", "airflow-webserver")
    ensure_health("http://localhost:9005/minio/health/live", "minio")
    ensure_health("http://localhost:8090/healthz", "cdn")

    log("2/5", "Проверка CDC-пайплайна")
    run_cdc_check()
    log("2/5", "CDC: ok")

    log("3/5", "Получение токенов Keycloak и подготовка тестового пользователя")
    admin_token = get_admin_token()
    user_id = keycloak_ensure_user(admin_token, SMOKE_USERNAME)
    keycloak_set_password(admin_token, user_id, SMOKE_PASSWORD)
    keycloak_clear_required_actions(admin_token, user_id)
    ensure_smoke_user_data()
    report_token = get_report_token(SMOKE_USERNAME, SMOKE_PASSWORD)

    log("4/5", "Проверка формирования отчета в report-api")
    status, _, body = http_request(
        "GET",
        "http://localhost:8001/reports",
        headers={"Authorization": f"Bearer {report_token}"},
        timeout=20.0,
    )
    if status != 200:
        fail(f"report-api /reports failed: status={status}, body={body}")
    report = json.loads(body)
    if report.get("report_status") != "ready":
        fail(f"Expected report_status=ready, got {report.get('report_status')}. body={body}")
    report_url = report.get("report_url")
    if not isinstance(report_url, str) or not report_url:
        fail(f"report_url missing in report-api response: {body}")
    log("4/5", f"Отчет готов для {report.get('report_owner', 'unknown')}")

    log("5/5", "Проверка CDN cache HIT по URL отчета")
    marker = "/reports-cache/"
    idx = report_url.find(marker)
    if idx < 0:
        fail(f"Unexpected report_url format: {report_url}")
    object_path = report_url[idx + len(marker):].lstrip("/")
    cdn_url = f"http://localhost:8090/reports-cache/{object_path}"
    minio_url = f"http://localhost:9005/bionicpro-reports/{object_path}"

    # После генерации отчёта объект может появиться в CDN с небольшой задержкой.
    # Делаем несколько попыток, чтобы исключить ложнопадающий smoke.
    headers1: dict[str, str] = {}
    headers2: dict[str, str] = {}
    status1 = 0
    status2 = 0
    for _ in range(12):
        status1, headers1, _ = http_request("GET", cdn_url, timeout=20.0)
        status2, headers2, _ = http_request("GET", cdn_url, timeout=20.0)
        if status1 == 200 and status2 == 200:
            break
        time.sleep(2)
    else:
        minio_status, _, minio_body = http_request("GET", minio_url, timeout=20.0)
        fail(
            "CDN response status invalid after retries: "
            f"first={status1}, second={status2}, minio_status={minio_status}, "
            f"minio_body_sample={minio_body[:200]}"
        )

    cache_second = headers2.get("x-cache-status", "")
    if cache_second != "HIT":
        fail(
            "Expected second CDN response X-Cache-Status=HIT, "
            f"got '{cache_second}'. first={headers1.get('x-cache-status', '')}, second={cache_second}"
        )

    print("System smoke passed: health, CDC, reports, CDN cache.")


if __name__ == "__main__":
    run()
