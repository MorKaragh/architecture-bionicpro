import json
import os
from datetime import datetime, timezone
from typing import Any

import psycopg2
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="profile-api")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://app_user:app_password@app_db:5432/app_db",
)
INTERNAL_SECRET = os.getenv("PROFILE_INTERNAL_SECRET", "change-me-profile-secret")


def _conn():
    return psycopg2.connect(DATABASE_URL)


def _require_secret(x_internal_secret: str | None) -> None:
    if not x_internal_secret or x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.on_event("startup")
def _migrate() -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
              keycloak_sub TEXT PRIMARY KEY,
              email TEXT,
              preferred_username TEXT,
              yandex_id TEXT,
              yandex_login TEXT,
              profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
              consent_given_at TIMESTAMPTZ,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        c.commit()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internal/profiles/{keycloak_sub}")
def get_profile(
    keycloak_sub: str,
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> JSONResponse:
    _require_secret(x_internal_secret)
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT keycloak_sub, email, preferred_username, yandex_id, yandex_login,
                   profile_json, consent_given_at, created_at, updated_at
            FROM user_profiles WHERE keycloak_sub = %s
            """,
            (keycloak_sub,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    consent_given_at = row[6]
    yandex_id = row[3]
    needs_consent = yandex_id is not None and consent_given_at is None
    return JSONResponse(
        {
            "keycloak_sub": row[0],
            "email": row[1],
            "preferred_username": row[2],
            "yandex_id": row[3],
            "yandex_login": row[4],
            "profile_json": row[5],
            "consent_given_at": consent_given_at.isoformat() if consent_given_at else None,
            "needs_consent": needs_consent,
        }
    )


@app.post("/internal/profiles/upsert")
def upsert_profile(
    body: dict[str, Any],
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> JSONResponse:
    _require_secret(x_internal_secret)
    sub = body.get("keycloak_sub")
    if not sub:
        raise HTTPException(status_code=400, detail="keycloak_sub required")
    email = body.get("email")
    preferred_username = body.get("preferred_username")
    yandex_id = body.get("yandex_id")
    yandex_login = body.get("yandex_login")
    profile_json: Any = body.get("profile_json") or {}
    if not isinstance(profile_json, dict):
        raise HTTPException(status_code=400, detail="profile_json must be object")
    now = datetime.now(timezone.utc)
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_profiles (
              keycloak_sub, email, preferred_username, yandex_id, yandex_login,
              profile_json, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (keycloak_sub) DO UPDATE SET
              email = COALESCE(EXCLUDED.email, user_profiles.email),
              preferred_username = COALESCE(EXCLUDED.preferred_username, user_profiles.preferred_username),
              yandex_id = COALESCE(EXCLUDED.yandex_id, user_profiles.yandex_id),
              yandex_login = COALESCE(EXCLUDED.yandex_login, user_profiles.yandex_login),
              profile_json = EXCLUDED.profile_json,
              updated_at = EXCLUDED.updated_at
            """,
            (
                sub,
                email,
                preferred_username,
                yandex_id,
                yandex_login,
                json.dumps(profile_json),
                now,
            ),
        )
        c.commit()
    return JSONResponse({"ok": True})


@app.post("/internal/profiles/{keycloak_sub}/consent")
def record_consent(
    keycloak_sub: str,
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> JSONResponse:
    _require_secret(x_internal_secret)
    now = datetime.now(timezone.utc)
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            UPDATE user_profiles
            SET consent_given_at = %s, updated_at = %s
            WHERE keycloak_sub = %s
            RETURNING keycloak_sub
            """,
            (now, now, keycloak_sub),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Profile not found")
        c.commit()
    return JSONResponse({"ok": True, "consent_given_at": now.isoformat()})
