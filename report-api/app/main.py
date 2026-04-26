import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import boto3
import clickhouse_connect
import jwt
from botocore.client import Config
from botocore.exceptions import ClientError
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
CLICKHOUSE_REPORT_TABLE = os.getenv("CLICKHOUSE_REPORT_TABLE", "reports.user_report_mart")

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadminsecret")
S3_BUCKET = os.getenv("S3_BUCKET", "bionicpro-reports")
CDN_PUBLIC_BASE_URL = os.getenv("CDN_PUBLIC_BASE_URL", "http://localhost:8090/reports-cache").rstrip("/")

_jwks_client: PyJWKClient | None = None
_ch_client = None
_s3_client = None


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
            password=CLICKHOUSE_PASSWORD or None,
        )
    return _ch_client


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _s3_client


def _safe_key_segment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value))
    return cleaned.strip("_") or "unknown"


def _data_as_of_slug(value: Any) -> str:
    if hasattr(value, "isoformat"):
        raw = value.isoformat()
    else:
        raw = str(value)
    return raw.replace(":", "-").replace("+", "_")


def _object_key(user_key: str, data_as_of: Any) -> str:
    slug = _data_as_of_slug(data_as_of)
    return f"reports/{_safe_key_segment(user_key)}/{slug}.json"


def _public_cdn_url(object_key: str) -> str:
    return f"{CDN_PUBLIC_BASE_URL}/{object_key}"


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


def _head_object_exists(key: str) -> bool:
    s3 = _get_s3()
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise HTTPException(status_code=502, detail=f"S3 head failed: {code}") from exc


def _get_report_json_from_s3(key: str) -> dict[str, Any]:
    s3 = _get_s3()
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        body = resp["Body"].read()
        return json.loads(body.decode("utf-8"))
    except ClientError as exc:
        raise HTTPException(status_code=502, detail="Unable to read report from S3") from exc


def _put_report_json_to_s3(key: str, payload: dict[str, Any]) -> None:
    s3 = _get_s3()
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=body,
            ContentType="application/json; charset=utf-8",
            CacheControl="public, max-age=3600",
        )
    except ClientError as exc:
        raise HTTPException(status_code=502, detail="Unable to store report in S3") from exc


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
    report_table = CLICKHOUSE_REPORT_TABLE
    watermark = ch.query(
        """
        SELECT data_as_of
        FROM {table}
        WHERE user_key = {{user_key:String}}
        ORDER BY data_as_of DESC
        LIMIT 1
        """.format(table=report_table),
        parameters={"user_key": str(user_key)},
    )
    wm_rows = watermark.result_rows
    generated_at = datetime.now(timezone.utc).isoformat()

    if not wm_rows:
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

    data_as_of = wm_rows[0][0]
    data_as_of_iso = data_as_of.isoformat() if hasattr(data_as_of, "isoformat") else str(data_as_of)
    object_key = _object_key(user_key, data_as_of)

    if _head_object_exists(object_key):
        stored = _get_report_json_from_s3(object_key)
        report_url = _public_cdn_url(object_key)
        return {
            **stored,
            "generated_at": generated_at,
            "report_url": report_url,
            "delivery": "s3_cache_hit",
            "cache": {"clickhouse": "watermark_only", "s3": "hit"},
        }

    metrics = ch.query(
        """
        SELECT
            prosthesis_uptime_hours,
            training_sessions,
            battery_cycles,
            crm_segment
        FROM {table}
        WHERE user_key = {{user_key:String}}
        ORDER BY data_as_of DESC
        LIMIT 1
        """.format(table=report_table),
        parameters={"user_key": str(user_key)},
    )
    mrows = metrics.result_rows
    if not mrows:
        return {
            "report_owner": user_key,
            "generated_at": generated_at,
            "report_status": "no_data",
            "data_as_of": None,
            "message": "Строка витрины исчезла между запросами (повторите попытку).",
        }

    uptime, sessions, cycles, segment = mrows[0]
    payload_body = {
        "report_owner": user_key,
        "report_status": "ready",
        "data_as_of": data_as_of_iso,
        "summary": {
            "prosthesis_uptime_hours": float(uptime),
            "training_sessions": int(sessions),
            "battery_cycles": int(cycles),
            "crm_segment": str(segment),
        },
    }
    _put_report_json_to_s3(object_key, payload_body)

    report_url = _public_cdn_url(object_key)
    return {
        **payload_body,
        "generated_at": generated_at,
        "report_url": report_url,
        "delivery": "generated_and_uploaded",
        "cache": {"clickhouse": "full_read", "s3": "write"},
    }
