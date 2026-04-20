import base64
import hashlib
import json
import os
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="bionicpro-auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KEYCLOAK_INTERNAL_URL = os.getenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
KEYCLOAK_PUBLIC_URL = os.getenv("KEYCLOAK_PUBLIC_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "bionicpro-auth")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "change-me")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
REPORT_API_URL = os.getenv("REPORT_API_URL", "http://report-api:8001")

COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "bionicpro_session")
COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))

PUBLIC_REALM_URL = f"{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}"
INTERNAL_REALM_URL = f"{KEYCLOAK_INTERNAL_URL}/realms/{KEYCLOAK_REALM}"
AUTH_URL = f"{PUBLIC_REALM_URL}/protocol/openid-connect/auth"
TOKEN_URL = f"{INTERNAL_REALM_URL}/protocol/openid-connect/token"
LOGOUT_URL = f"{INTERNAL_REALM_URL}/protocol/openid-connect/logout"
CALLBACK_URL = os.getenv("AUTH_CALLBACK_URL", "http://localhost:8000/auth/callback")

sessions: dict[str, dict[str, Any]] = {}
OAUTH_STATE_COOKIE = "bp_oauth_state"
OAUTH_VERIFIER_COOKIE = "bp_oauth_verifier"
OAUTH_COOKIE_TTL_SECONDS = 300


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _new_session_id() -> str:
    return secrets.token_urlsafe(32)


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload_raw = base64.urlsafe_b64decode(payload_b64 + padding)
        return json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return {}


def _cookie_kwargs() -> dict[str, Any]:
    return {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "max_age": SESSION_TTL_SECONDS,
        "path": "/",
    }


def _get_active_session(request: Request) -> tuple[str, dict[str, Any]]:
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = sessions[session_id]
    if session["expires_at"] < time.time():
        sessions.pop(session_id, None)
        raise HTTPException(status_code=401, detail="Session expired")

    return session_id, session


async def _refresh_access_token_if_needed(session: dict[str, Any]) -> None:
    if session["access_expires_at"] - 5 > time.time():
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": KEYCLOAK_CLIENT_ID,
                "client_secret": KEYCLOAK_CLIENT_SECRET,
                "refresh_token": session["refresh_token"],
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Unable to refresh session")

    token_data = resp.json()
    now_ts = time.time()
    session["access_token"] = token_data["access_token"]
    session["refresh_token"] = token_data.get("refresh_token", session["refresh_token"])
    session["access_expires_at"] = now_ts + int(token_data.get("expires_in", 60))
    session["expires_at"] = now_ts + SESSION_TTL_SECONDS


def _rotate_session(old_session_id: str, session: dict[str, Any], response: Response) -> str:
    new_session_id = _new_session_id()
    sessions[new_session_id] = session
    sessions.pop(old_session_id, None)
    response.set_cookie(COOKIE_NAME, new_session_id, **_cookie_kwargs())
    return new_session_id


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/login")
async def auth_login() -> RedirectResponse:
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce_pair()
    query = urlencode(
        {
            "response_type": "code",
            "client_id": KEYCLOAK_CLIENT_ID,
            "scope": "openid profile email",
            "redirect_uri": CALLBACK_URL,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    resp = RedirectResponse(url=f"{AUTH_URL}?{query}", status_code=302)
    resp.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=OAUTH_COOKIE_TTL_SECONDS,
        path="/",
    )
    resp.set_cookie(
        OAUTH_VERIFIER_COOKIE,
        verifier,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=OAUTH_COOKIE_TTL_SECONDS,
        path="/",
    )
    return resp


@app.get("/auth/callback")
async def auth_callback(code: str, state: str, request: Request) -> RedirectResponse:
    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
    verifier = request.cookies.get(OAUTH_VERIFIER_COOKIE)
    if not cookie_state or not verifier or cookie_state != state:
        raise HTTPException(status_code=400, detail="Invalid auth state")

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": KEYCLOAK_CLIENT_ID,
                "client_secret": KEYCLOAK_CLIENT_SECRET,
                "code": code,
                "redirect_uri": CALLBACK_URL,
                "code_verifier": verifier,
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Code exchange failed")
        token_data = token_resp.json()

        userinfo = _decode_jwt_payload(token_data["access_token"])
        if not userinfo.get("sub"):
            raise HTTPException(status_code=401, detail="Unable to parse user token")

    now_ts = time.time()
    session_id = _new_session_id()
    sessions[session_id] = {
        "user": {
            "sub": userinfo.get("sub"),
            "preferred_username": userinfo.get("preferred_username"),
            "email": userinfo.get("email"),
        },
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token"),
        "access_expires_at": now_ts + int(token_data.get("expires_in", 60)),
        "expires_at": now_ts + SESSION_TTL_SECONDS,
    }

    resp = RedirectResponse(url=FRONTEND_BASE_URL, status_code=302)
    resp.set_cookie(COOKIE_NAME, session_id, **_cookie_kwargs())
    resp.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    resp.delete_cookie(OAUTH_VERIFIER_COOKIE, path="/")
    return resp


@app.get("/auth/me")
async def auth_me(request: Request) -> JSONResponse:
    old_sid, session = _get_active_session(request)
    await _refresh_access_token_if_needed(session)
    resp = JSONResponse({"authenticated": True, "user": session["user"]})
    _rotate_session(old_sid, session, resp)
    return resp


@app.post("/auth/logout")
async def auth_logout(request: Request) -> JSONResponse:
    session_id = request.cookies.get(COOKIE_NAME)
    session = sessions.pop(session_id, None) if session_id else None

    if session and session.get("refresh_token"):
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                LOGOUT_URL,
                data={
                    "client_id": KEYCLOAK_CLIENT_ID,
                    "client_secret": KEYCLOAK_CLIENT_SECRET,
                    "refresh_token": session["refresh_token"],
                },
            )

    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


@app.get("/reports")
async def get_report(request: Request) -> JSONResponse:
    old_sid, session = _get_active_session(request)
    await _refresh_access_token_if_needed(session)

    async with httpx.AsyncClient(timeout=15.0) as client:
        report_resp = await client.get(
            f"{REPORT_API_URL}/reports",
            headers={"Authorization": f"Bearer {session['access_token']}"},
        )
    if report_resp.status_code != 200:
        raise HTTPException(status_code=report_resp.status_code, detail=report_resp.text)

    payload = report_resp.json()
    response = JSONResponse(payload)
    _rotate_session(old_sid, session, response)
    return response
