#!/usr/bin/env python3
import base64
import json
import urllib.parse
import urllib.request


def post(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def decode_jwt_payload(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))


def userinfo(token: str) -> dict:
    req = urllib.request.Request(
        "http://localhost:8080/realms/reports-realm/protocol/openid-connect/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    token_resp = post(
        "http://localhost:8080/realms/reports-realm/protocol/openid-connect/token",
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": "prothetic1",
            "password": "prothetic123",
        },
    )
    token = token_resp["access_token"]

    claims = decode_jwt_payload(token)
    print("TOKEN_CLAIMS_KEYS:", sorted(claims.keys()))
    print("TOKEN_CLAIMS:", json.dumps(claims, ensure_ascii=False))

    ui = userinfo(token)
    print("USERINFO_KEYS:", sorted(ui.keys()))
    print("USERINFO:", json.dumps(ui, ensure_ascii=False))


if __name__ == "__main__":
    main()
