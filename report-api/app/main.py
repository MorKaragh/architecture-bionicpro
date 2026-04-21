import os
from datetime import datetime, timezone

import clickhouse_connect
import jwt
from fastapi import FastAPI, Header, HTTPException
from jwt import PyJWKClient

app = FastAPI(title="report-api")

KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
JWKS_URL = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"

EXPECTED_ISS = os.getenv(
    "KEYCLOAK_EXPECTED_ISS",
    "http://localhost:8080/realms/reports-realm,http://keycloak:8080/realms/reports-realm",
)

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_HTTP_PORT = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")

_jwks_client: PyJWKClient | None = None
_ch_client = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(JWKS_URL)
    return _jwks_client


def _get_clickhouse():
    global _ch_client
    if _ch_client is None:
        _ch_client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_HTTP_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
        )
    return _ch_client


def _validate_access_token(token: str) -> dict:
    allowed_iss = {s.strip() for s in EXPECTED_ISS.split(",") if s.strip()}
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False},
        )
        if allowed_iss and payload.get("iss") not in allowed_iss:
            raise HTTPException(status_code=401, detail="Unexpected token issuer")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/reports")
async def get_report(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    claims = _validate_access_token(token)

    user_key = claims.get("preferred_username") or claims.get("username")
    if not user_key:
        raise HTTPException(status_code=401, detail="Token has no user identifier")

    ch = _get_clickhouse()
    result = ch.query(
        """
        SELECT
            prosthesis_uptime_hours,
            training_sessions,
            battery_cycles,
            crm_segment,
            data_as_of
        FROM reports.user_report_mart
        WHERE user_key = {user_key:String}
        LIMIT 1
        """,
        parameters={"user_key": str(user_key)},
    )
    rows = result.result_rows
    generated_at = datetime.now(timezone.utc).isoformat()

    if not rows:
        return {
            "report_owner": user_key,
            "generated_at": generated_at,
            "report_status": "no_data",
            "data_as_of": None,
            "message": (
                "В витрине отчётности пока нет строк для этого пользователя "
                "(дождитесь прогона ETL в Airflow или проверьте сопоставление user_key с Keycloak)."
            ),
        }

    uptime, sessions, cycles, segment, data_as_of = rows[0]
    data_as_of_iso = data_as_of.isoformat() if hasattr(data_as_of, "isoformat") else str(data_as_of)

    return {
        "report_owner": user_key,
        "generated_at": generated_at,
        "report_status": "ready",
        "data_as_of": data_as_of_iso,
        "summary": {
            "prosthesis_uptime_hours": float(uptime),
            "training_sessions": int(sessions),
            "battery_cycles": int(cycles),
            "crm_segment": str(segment),
        },
    }
