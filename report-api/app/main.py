import os
from datetime import datetime, timezone

import jwt
from fastapi import FastAPI, Header, HTTPException
from jwt import PyJWKClient

app = FastAPI(title="report-api")

KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
JWKS_URL = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"

# Ожидаемый iss в access token (в dev часто http://localhost:8080/realms/...).
# Через запятую можно задать несколько значений.
EXPECTED_ISS = os.getenv(
    "KEYCLOAK_EXPECTED_ISS",
    "http://localhost:8080/realms/reports-realm,http://keycloak:8080/realms/reports-realm",
)

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(JWKS_URL)
    return _jwks_client


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

    username = claims.get("preferred_username") or claims.get("username") or "unknown"
    return {
        "report_owner": username,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "prosthesis_uptime_hours": 128,
            "training_sessions": 12,
            "battery_cycles": 45,
        },
        "note": "Demo report payload. Replace with ClickHouse query results in Task2/Task3.",
    }
