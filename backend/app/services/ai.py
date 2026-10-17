"""Provider boundary: external I/O exists only behind explicit per-request consent."""

import ast
import hashlib
import json
import math
import operator
import os
from typing import Protocol
import httpx
from fastapi import HTTPException
from .settings import SettingsInput, settings


class AIUnavailable(Exception):
    pass


class ModelProvider(Protocol):
    def complete(self, messages: list[dict]) -> str: ...


class CompatibleProvider:
    def __init__(self, base_url, model, key, timeout=45, transport=None):
        self.base_url, self.model, self.key, self.timeout = (
            base_url,
            model,
            key,
            timeout,
        )
        self.transport = transport

    def complete(self, messages):
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST",
                    self.base_url + "/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "max_tokens": 2048,
                    },
                ) as response:
                    if response.status_code in (401, 403):
                        raise HTTPException(
                            502, "模型服务拒绝认证，请检查服务端密钥与模型权限。"
                        )
                    if response.status_code == 429:
                        raise HTTPException(503, "模型服务限流或额度不足；未自动重试。")
                    if not 200 <= response.status_code < 300:
                        raise HTTPException(
                            502,
                            f"模型服务返回 HTTP {response.status_code}，未自动重试。",
                        )
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 2_000_000:
                            raise HTTPException(502, "模型响应超过安全长度限制。")
            value = json.loads(raw)
            answer = value["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("empty content")
            return answer
        except httpx.TimeoutException as exc:
            raise HTTPException(
                504, "模型请求超时；未自动重试，服务商仍可能计费。"
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, "无法连接模型服务，请检查地址和网络。") from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise HTTPException(502, "模型响应不符合兼容接口格式。") from exc


def configuration(conn):
    prefs = settings(conn)
    base = os.getenv("YANTU_AI_BASE_URL", prefs.ai_base_url).rstrip("/")
    model = os.getenv("YANTU_AI_MODEL", prefs.ai_model)
    # Environment configuration is subject to the same transport policy as the UI.
    if base:
        SettingsInput(ai_base_url=base)
    key = os.getenv("YANTU_AI_API_KEY", "")
    return base, model, key, prefs.ai_timeout


def status(conn):
    base, model, key, _ = configuration(conn)
    available = bool(base and model and key)
    return {
        "available": available,
        "provider": "compatible" if available else None,
        "base_url": base,
        "model": model,
        "key_configured": bool(key),
        "message": "模型接口已配置；每次发送前需确认数据范围，尚未代表连通性已验证。"
        if available
        else "尚未接入真实 AI 服务。请配置服务地址、模型和服务端 YANTU_AI_API_KEY；基础学习功能不受影响。",
    }


def digest(payload):
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def verify_arithmetic(expression):
    """Bounded numeric arithmetic only. No eval, functions, variables, or generated code."""
    if len(expression) > 200:
        raise ValueError("算式过长")

    def calculate(text):
        tree = ast.parse(text.strip(), mode="eval")
        if len(list(ast.walk(tree))) > 50:
            raise ValueError("算式过于复杂")

        def visit(node):
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                value = node.value
            elif isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.UAdd, ast.USub)
            ):
                value = visit(node.operand) * (
                    1 if isinstance(node.op, ast.UAdd) else -1
                )
            elif isinstance(node, ast.BinOp) and type(node.op) in (
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.Pow,
            ):
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and (
                    abs(right) > 30 or abs(left) > 1e6
                ):
                    raise ValueError("幂运算超出限制")
                value = {
                    ast.Add: operator.add,
                    ast.Sub: operator.sub,
                    ast.Mult: operator.mul,
                    ast.Div: operator.truediv,
                    ast.Pow: operator.pow,
                }[type(node.op)](left, right)
            else:
                raise ValueError("仅支持数字、括号、+ - * / **，不执行代码或函数")
            if (
                isinstance(value, complex)
                or not math.isfinite(value)
                or abs(value) > 1e15
            ):
                raise ValueError("数值超出范围")
            return value

        return visit(tree)

    parts = expression.split("=")
    if len(parts) > 2:
        raise ValueError("只能比较等式两侧")
    left = calculate(parts[0])
    right = calculate(parts[1]) if len(parts) == 2 else None
    return {
        "source": "local_arithmetic",
        "value": left,
        "equal": math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
        if right is not None
        else None,
        "note": "仅核对数值计算，不证明推导、定义域或一般数学结论。",
    }
