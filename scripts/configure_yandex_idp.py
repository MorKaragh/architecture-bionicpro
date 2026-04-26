#!/usr/bin/env python3
"""
Создаёт/обновляет Identity Provider «Яндекс» в Keycloak.

Используется провайдер **yandex** из JAR `keycloak-russian-providers` (OAuth2 к Яндексу,
без принудительного scope `openid`, из‑за которого встроенный OIDC-брокер даёт invalid_scope).

Мапперы:
- id / login -> атрибуты yandex_id / yandex_login
- protocol mapper на клиенте bionicpro-auth: атрибуты в userinfo/token

Нужны переменные окружения:
  KEYCLOAK_URL          (по умолчанию http://localhost:8080)
  KEYCLOAK_REALM        (по умолчанию reports-realm)
  KEYCLOAK_ADMIN        KEYCLOAK_ADMIN_PASSWORD
  YANDEX_CLIENT_ID      YANDEX_CLIENT_SECRET

Запуск с хоста: python3 scripts/configure_yandex_idp.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _req(
    method: str,
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    token: str | None = None,
) -> tuple[int, bytes]:
    h = dict(headers or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    if data is not None and "Content-Type" not in h:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main() -> int:
    base = os.getenv("KEYCLOAK_URL", "http://localhost:8080").rstrip("/")
    realm = os.getenv("KEYCLOAK_REALM", "reports-realm")
    admin = os.getenv("KEYCLOAK_ADMIN", "admin")
    admin_pass = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
    client_id = os.getenv("YANDEX_CLIENT_ID", "").strip()
    client_secret = os.getenv("YANDEX_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print(
            "Задайте YANDEX_CLIENT_ID и YANDEX_CLIENT_SECRET (приложение в кабинете Яндекса OAuth).",
            file=sys.stderr,
        )
        return 1

    code, body = _req(
        "POST",
        f"{base}/realms/master/protocol/openid-connect/token",
        data=urllib.parse.urlencode(
            {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": admin,
                "password": admin_pass,
            }
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if code != 200:
        print(f"Не удалось получить admin token: HTTP {code} {body.decode()}", file=sys.stderr)
        return 1
    token = json.loads(body.decode())["access_token"]

    admin_realm = f"{base}/admin/realms/{realm}"

    # Удаляем старый IdP с тем же alias, если есть
    code, body = _req("GET", f"{admin_realm}/identity-provider/instances", token=token)
    if code == 200:
        for inst in json.loads(body.decode()):
            if inst.get("alias") == "yandex":
                _req("DELETE", f"{admin_realm}/identity-provider/instances/yandex", token=token)
                break

    idp_payload = {
        "alias": "yandex",
        "displayName": "Яндекс",
        "providerId": "yandex",
        "enabled": True,
        "trustEmail": True,
        "storeToken": False,
        "addReadTokenRoleOnCreate": False,
        "authenticateByDefault": False,
        "linkOnly": False,
        "firstBrokerLoginFlowAlias": "first broker login",
        # getDefaultScopes() в JAR пустой; без defaultScope Яндекс не отдаёт default_email в /info,
        # а YandexIdentityProvider бросает исключение, если email пустой.
        "config": {
            "clientId": client_id,
            "clientSecret": client_secret,
            "defaultScope": "login:info login:email",
            "hideOnLoginPage": "false",
            "guiOrder": "0",
        },
    }

    code, body = _req(
        "POST",
        f"{admin_realm}/identity-provider/instances",
        data=json.dumps(idp_payload).encode(),
        token=token,
    )
    if code not in (200, 201):
        print(f"Создание IdP: HTTP {code} {body.decode()}", file=sys.stderr)
        return 1

    code, body = _req("GET", f"{admin_realm}/identity-provider/instances/yandex", token=token)
    if code == 200:
        inst = json.loads(body.decode())
        print(
            "Провайдер в Keycloak:",
            "alias=",
            inst.get("alias"),
            "enabled=",
            inst.get("enabled"),
            "displayName=",
            inst.get("displayName"),
            "hideOnLoginPage=",
            (inst.get("config") or {}).get("hideOnLoginPage"),
        )

    # yandex-user-attribute-mapper (keycloak-russian-providers) ждёт ключи jsonField / userAttribute,
    # не claim / user.attribute как у встроенного oidc-user-attribute-idp-mapper.
    mappers = [
        {
            "name": "yandex-id",
            "identityProviderAlias": "yandex",
            "identityProviderMapper": "yandex-user-attribute-mapper",
            "config": {
                "syncMode": "INHERIT",
                "jsonField": "id",
                "userAttribute": "yandex_id",
            },
        },
        {
            "name": "yandex-login",
            "identityProviderAlias": "yandex",
            "identityProviderMapper": "yandex-user-attribute-mapper",
            "config": {
                "syncMode": "INHERIT",
                "jsonField": "login",
                "userAttribute": "yandex_login",
            },
        },
    ]
    for m in mappers:
        code, body = _req(
            "POST",
            f"{admin_realm}/identity-provider/instances/yandex/mappers",
            data=json.dumps(m).encode(),
            token=token,
        )
        if code not in (200, 201):
            print(f"Mapper {m['name']}: HTTP {code} {body.decode()}", file=sys.stderr)
            return 1

    # Protocol mappers на клиенте bionicpro-auth — атрибуты в userinfo
    code, body = _req("GET", f"{admin_realm}/clients?clientId=bionicpro-auth", token=token)
    if code != 200:
        print(f"Поиск клиента: HTTP {code}", file=sys.stderr)
        return 1
    clients = json.loads(body.decode())
    if not clients:
        print("Клиент bionicpro-auth не найден", file=sys.stderr)
        return 1
    internal_id = clients[0]["id"]

    code, body = _req(
        "GET",
        f"{admin_realm}/clients/{internal_id}/protocol-mappers/models",
        token=token,
    )
    existing = json.loads(body.decode()) if code == 200 else []
    for name in ("yandex-id-userinfo", "yandex-login-userinfo"):
        for pm in existing:
            if pm.get("name") == name:
                _req(
                    "DELETE",
                    f"{admin_realm}/clients/{internal_id}/protocol-mappers/models/{pm['id']}",
                    token=token,
                )
                break

    for attr, claim_name, title in (
        ("yandex_id", "yandex_id", "yandex-id-userinfo"),
        ("yandex_login", "yandex_login", "yandex-login-userinfo"),
    ):
        pm_payload = {
            "name": title,
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-attribute-mapper",
            "consentRequired": False,
            "config": {
                "user.attribute": attr,
                "claim.name": claim_name,
                "jsonType.label": "String",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
            },
        }
        code, body = _req(
            "POST",
            f"{admin_realm}/clients/{internal_id}/protocol-mappers/models",
            data=json.dumps(pm_payload).encode(),
            token=token,
        )
        if code not in (200, 201):
            print(f"Protocol mapper {title}: HTTP {code} {body.decode()}", file=sys.stderr)
            return 1

    print("Yandex IdP и мапперы настроены. Redirect URI в кабинете Яндекса:")
    print(f"  {base}/realms/{realm}/broker/yandex/endpoint")
    return 0


if __name__ == "__main__":
    sys.exit(main())
