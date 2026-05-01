#!/usr/bin/env python3
import argparse
import base64
import json
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class HttpResult:
    status: int
    headers: dict[str, str]
    body: str


class ShowcaseError(RuntimeError):
    pass


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 20.0,
) -> HttpResult:
    print_request_preview(method, url, headers=headers, data=data)
    req = urllib.request.Request(url, method=method, data=data)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return HttpResult(
                status=resp.status,
                headers={k.lower(): v for k, v in resp.headers.items()},
                body=resp.read().decode("utf-8", errors="replace"),
            )
    except urllib.error.HTTPError as err:
        return HttpResult(
            status=err.code,
            headers={k.lower(): v for k, v in err.headers.items()},
            body=err.read().decode("utf-8", errors="replace"),
        )


def post_form(url: str, payload: dict[str, str]) -> HttpResult:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    return request(
        "POST",
        url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=data,
    )


def print_box(title: str, demonstrates: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("-" * 88)
    print(f"Что демонстрируем: {demonstrates}")
    print("=" * 88)


def shorten(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated] ..."


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def print_result(
    result: HttpResult,
    *,
    body_limit: int,
    interesting_headers: list[str] | None = None,
) -> None:
    print(f"HTTP {result.status}")
    headers = interesting_headers or []
    for name in headers:
        v = result.headers.get(name.lower())
        if v:
            print(f"{name}: {v}")
    body = shorten(result.body.strip() or "<empty>", body_limit)
    print("\n" + body)


def print_request_preview(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> None:
    print("\nREQUEST")
    print(f"{method} {url}")
    if headers:
        print("Headers:")
        for k, v in headers.items():
            print(f"  {k}: {v}")
    if data:
        body_preview = data.decode("utf-8", errors="replace")
        print("Body:")
        print(shorten(body_preview, 600))


def parse_json_body(result: HttpResult) -> dict[str, Any]:
    try:
        return json.loads(result.body)
    except json.JSONDecodeError as exc:
        raise ShowcaseError(f"Ожидался JSON, но пришло не-JSON (HTTP {result.status})") from exc


def decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def choose_report_token(token_response: dict[str, Any]) -> str:
    candidates = [token_response.get("id_token"), token_response.get("access_token")]
    for token in candidates:
        if not token:
            continue
        payload = decode_jwt_payload(token)
        if payload.get("preferred_username") or payload.get("username"):
            return token
    raise ShowcaseError(
        "Не удалось выбрать токен с user identifier: "
        "в id_token/access_token нет preferred_username/username"
    )


def maybe_pause(enabled: bool) -> None:
    if enabled:
        input("\nНажмите Enter для следующего шага...")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Красивый прогон запросов для скриншотов ревью (Task1-Task4)."
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Пауза после каждого шага (удобно для скриншотов).",
    )
    parser.add_argument(
        "--body-limit",
        type=int,
        default=1200,
        help="Максимум символов тела ответа в выводе (по умолчанию: 1200).",
    )
    args = parser.parse_args()

    base_auth = "http://localhost:8000"
    base_report_api = "http://localhost:8001"
    base_profile_api = "http://localhost:8002"
    base_keycloak = "http://localhost:8080"
    base_clickhouse = "http://localhost:8123"
    base_kafka_connect = "http://localhost:8083"
    base_minio = "http://localhost:9005"
    base_cdn = "http://localhost:8090"

    try:
        print_box(
            "TASK 1.1 — BFF health",
            "BFF (bionicpro-auth) поднят и отвечает healthcheck.",
        )
        r = request("GET", f"{base_auth}/healthz")
        print_result(r, body_limit=args.body_limit)
        maybe_pause(args.pause)

        print_box(
            "TASK 1.2 — Profile API health",
            "Profile API поднят и отвечает healthcheck.",
        )
        r = request("GET", f"{base_profile_api}/healthz")
        print_result(r, body_limit=args.body_limit)
        maybe_pause(args.pause)

        print_box(
            "TASK 1.3 — Keycloak discovery",
            "Realm reports-realm доступен (OIDC discovery).",
        )
        r = request("GET", f"{base_keycloak}/realms/reports-realm/.well-known/openid-configuration")
        discovery = parse_json_body(r)
        compact = {
            "issuer": discovery.get("issuer"),
            "authorization_endpoint": discovery.get("authorization_endpoint"),
            "token_endpoint": discovery.get("token_endpoint"),
            "userinfo_endpoint": discovery.get("userinfo_endpoint"),
            "jwks_uri": discovery.get("jwks_uri"),
        }
        print(f"HTTP {r.status}\n\n{pretty_json(compact)}")
        maybe_pause(args.pause)

        print_box(
            "TASK 1.4 — Получение пользовательского токена",
            "Keycloak выдает токены для пользователя prothetic1.",
        )
        token_res = post_form(
            f"{base_keycloak}/realms/reports-realm/protocol/openid-connect/token",
            {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "prothetic1",
                "password": "prothetic123",
                "scope": "openid profile email",
            },
        )
        token_json = parse_json_body(token_res)
        token_preview = {
            "token_type": token_json.get("token_type"),
            "expires_in": token_json.get("expires_in"),
            "scope": token_json.get("scope"),
            "has_access_token": bool(token_json.get("access_token")),
            "has_id_token": bool(token_json.get("id_token")),
        }
        print(f"HTTP {token_res.status}\n\n{pretty_json(token_preview)}")
        report_token = choose_report_token(token_json)
        maybe_pause(args.pause)

        print_box(
            "TASK 2.1 — Report API",
            "Формирование пользовательского отчета и выдача report_url.",
        )
        report_res = request(
            "GET",
            f"{base_report_api}/reports",
            headers={"Authorization": f"Bearer {report_token}"},
        )
        report_json = parse_json_body(report_res)
        report_preview = {
            "report_owner": report_json.get("report_owner"),
            "report_status": report_json.get("report_status"),
            "data_as_of": report_json.get("data_as_of"),
            "delivery": report_json.get("delivery"),
            "report_url": report_json.get("report_url"),
        }
        print(f"HTTP {report_res.status}\n\n{pretty_json(report_preview)}")
        maybe_pause(args.pause)

        print_box(
            "TASK 2.2 — Витрина ClickHouse",
            "В reports.user_report_mart_cdc есть актуальные строки.",
        )
        ch_query = textwrap.dedent(
            """
            SELECT user_key, crm_segment, data_as_of
            FROM reports.user_report_mart_cdc
            ORDER BY data_as_of DESC
            LIMIT 8
            FORMAT JSON
            """
        ).strip()
        ch_res = request(
            "POST",
            f"{base_clickhouse}/?user=reports&password=reports_password",
            headers={"Content-Type": "text/plain"},
            data=ch_query.encode("utf-8"),
        )
        ch_json = parse_json_body(ch_res)
        ch_preview = {"rows": ch_json.get("rows", 0), "data": ch_json.get("data", [])}
        print(f"HTTP {ch_res.status}\n\n{shorten(pretty_json(ch_preview), args.body_limit)}")
        maybe_pause(args.pause)

        report_url = report_json.get("report_url")
        if not isinstance(report_url, str) or "/reports-cache/" not in report_url:
            raise ShowcaseError("В ответе report-api нет корректного report_url.")
        object_path = report_url.split("/reports-cache/", 1)[1].lstrip("/")

        print_box(
            "TASK 3.1 — Объект в MinIO",
            "Отчет реально сохранен в bucket bionicpro-reports.",
        )
        minio_res = request("GET", f"{base_minio}/bionicpro-reports/{object_path}")
        print_result(minio_res, body_limit=args.body_limit)
        maybe_pause(args.pause)

        print_box(
            "TASK 3.2 / 3.3 — CDN cache",
            "Первый и второй запрос к CDN; второй должен быть HIT.",
        )
        cdn_1 = request(
            "GET",
            f"{base_cdn}/reports-cache/{object_path}",
            headers={"Accept-Encoding": "identity"},
        )
        print("Первый запрос:")
        print_result(
            cdn_1,
            body_limit=350,
            interesting_headers=["X-Cache-Status", "Content-Type"],
        )
        print("\n---\n")
        cdn_2 = request(
            "GET",
            f"{base_cdn}/reports-cache/{object_path}",
            headers={"Accept-Encoding": "identity"},
        )
        print("Второй запрос:")
        print_result(
            cdn_2,
            body_limit=350,
            interesting_headers=["X-Cache-Status", "Content-Type"],
        )
        maybe_pause(args.pause)

        print_box(
            "TASK 4.1 — Kafka Connect status",
            "CDC-коннектор crm-connector находится в RUNNING.",
        )
        kc_res = request("GET", f"{base_kafka_connect}/connectors/crm-connector/status")
        kc_json = parse_json_body(kc_res)
        kc_preview = {
            "name": kc_json.get("name"),
            "connector_state": kc_json.get("connector", {}).get("state"),
            "tasks": kc_json.get("tasks", []),
        }
        print(f"HTTP {kc_res.status}\n\n{pretty_json(kc_preview)}")
        maybe_pause(args.pause)

        print_box(
            "TASK 4.2 — CDC данные в витрине",
            "Изменения CRM видны в user_report_mart_cdc для user1.",
        )
        cdc_query = textwrap.dedent(
            """
            SELECT crm_segment, data_as_of
            FROM reports.user_report_mart_cdc
            WHERE user_key = 'user1'
            ORDER BY data_as_of DESC
            LIMIT 5
            FORMAT JSON
            """
        ).strip()
        cdc_res = request(
            "POST",
            f"{base_clickhouse}/?user=reports&password=reports_password",
            headers={"Content-Type": "text/plain"},
            data=cdc_query.encode("utf-8"),
        )
        cdc_json = parse_json_body(cdc_res)
        print(f"HTTP {cdc_res.status}\n\n{shorten(pretty_json(cdc_json), args.body_limit)}")

        print("\n✅ Готово. Все шаги выполнены. Можно делать финальные скриншоты.")
        return 0
    except ShowcaseError as exc:
        print(f"\n❌ Ошибка сценария: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ Непредвиденная ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
