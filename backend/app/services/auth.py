"""Single-user, expiring sessions. No account database or third-party identity service."""

from datetime import timedelta
import hashlib
import hmac
import secrets
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field
from ..schemas import Input


class LoginInput(Input):
    token: str = Field(min_length=1, max_length=1000)


class Auth:
    def __init__(self, token, now):
        self.token = token
        self.now = now
        self.sessions = {}
        self.failures = {}

    def authenticated(self, request):
        if not self.token:
            return request.client is not None and request.client.host in (
                "127.0.0.1",
                "::1",
                "testclient",
            )
        if hmac.compare_digest(
            request.headers.get("authorization", "").encode(),
            f"Bearer {self.token}".encode(),
        ):
            return True
        value = request.cookies.get("yantu_session", "")
        expiry = (
            self.sessions.get(hashlib.sha256(value.encode()).hexdigest())
            if value
            else None
        )
        return bool(expiry and expiry > self.now())

    def router(self):
        api = APIRouter(prefix="/api/auth")

        @api.post("/login")
        def login(data: LoginInput, request: Request, response: Response):
            ip = request.client.host if request.client else "unknown"
            now = self.now()
            self.failures = {
                key: [x for x in values if x > now - timedelta(minutes=5)]
                for key, values in self.failures.items()
                if any(x > now - timedelta(minutes=5) for x in values)
            }
            if len(self.failures.get(ip, [])) >= 10:
                raise HTTPException(429, "尝试次数过多，请五分钟后重试。")
            if not self.token or not hmac.compare_digest(
                data.token.encode(), self.token.encode()
            ):
                self.failures.setdefault(ip, []).append(now)
                raise HTTPException(401, "访问令牌不正确。")
            self.failures.pop(ip, None)
            self.sessions = {k: v for k, v in self.sessions.items() if v > now}
            value = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(value.encode()).hexdigest()] = now + timedelta(
                hours=24
            )
            response.set_cookie(
                "yantu_session",
                value,
                max_age=86400,
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="strict",
                path="/",
            )
            return {"authenticated": True, "expires_in": 86400}

        @api.post("/logout")
        def logout(request: Request, response: Response):
            value = request.cookies.get("yantu_session", "")
            self.sessions.pop(hashlib.sha256(value.encode()).hexdigest(), None)
            response.delete_cookie("yantu_session", path="/")
            return {"ok": True}

        @api.get("/status")
        def status(request: Request):
            return {
                "required": bool(self.token),
                "authenticated": self.authenticated(request),
            }

        return api
