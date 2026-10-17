"""Validated, non-secret preferences. Credentials live only in the environment."""

from typing import Literal
from pydantic import Field, field_validator
from ..schemas import Input


class SettingsInput(Input):
    exam_scope: Literal["unset", "math1", "math2", "math3"] = "unset"
    review_intervals: list[int] = Field(
        default=[1, 3, 7, 14, 30], min_length=5, max_length=5
    )
    pomodoro_minutes: int = Field(default=25, ge=1, le=180)
    break_minutes: int = Field(default=5, ge=1, le=60)
    ai_base_url: str = Field(default="", max_length=500)
    ai_model: str = Field(default="", max_length=200)
    ai_timeout: int = Field(default=45, ge=5, le=120)

    @field_validator("review_intervals")
    @classmethod
    def intervals(cls, v):
        if any(x < 1 or x > 365 for x in v) or v != sorted(set(v)):
            raise ValueError("需填写 5 个严格递增的 1–365 天间隔")
        return v

    @field_validator("ai_base_url")
    @classmethod
    def url(cls, v):
        from urllib.parse import urlparse

        if not v:
            return v
        p = urlparse(v)
        if (
            p.scheme not in ("https", "http")
            or not p.hostname
            or p.username
            or p.password
            or p.query
            or p.fragment
        ):
            raise ValueError("模型地址必须是无凭据、查询参数或片段的 HTTP(S) 地址")
        if p.scheme == "http" and p.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("远程模型服务必须使用 HTTPS")
        return v.rstrip("/")


def settings(conn):
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key='preferences'"
    ).fetchone()
    return SettingsInput.model_validate_json(row[0]) if row else SettingsInput()


def save_settings(conn, data):
    conn.execute(
        "INSERT INTO app_settings VALUES ('preferences',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (data.model_dump_json(),),
    )


def event(conn, kind, entity_id, value, stamp):
    conn.execute(
        "INSERT INTO activity_events(kind,entity_id,value,happened_at) VALUES (?,?,?,?)",
        (kind, entity_id, value, stamp),
    )
