#!/usr/bin/env python3
"""Real subprocess lifecycle + persistence + backup/restore + verified local TLS.
Every operation uses a temporary database, runtime directory and loopback port.
"""

import json
import os
from pathlib import Path
import socket
import sqlite3
import ssl
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / ".venv/bin/python")


def run(script, *args, env):
    p = subprocess.run(
        [PYTHON, str(ROOT / "scripts" / script), *args],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=40,
    )
    if p.returncode:
        raise AssertionError(script + " failed: " + p.stdout + p.stderr)
    return p.stdout


def request(url, path, body=None, token="", ca=None):
    handlers = [urllib.request.ProxyHandler({})]
    if ca:
        handlers.append(
            urllib.request.HTTPSHandler(
                context=ssl.create_default_context(cafile=str(ca))
            )
        )
    opener = urllib.request.build_opener(*handlers)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        url + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
    )
    with opener.open(req, timeout=5) as response:
        return json.load(response)


with tempfile.TemporaryDirectory(prefix="yantu-lifecycle-") as temp:
    folder = Path(temp)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "YANTU_DATABASE_PATH": str(folder / "data/yantu.sqlite3"),
        "YANTU_RUNTIME_DIR": str(folder / "runtime"),
        "YANTU_HOST": "127.0.0.1",
        "YANTU_PORT": str(port),
        "YANTU_ACCESS_TOKEN": "",
        "YANTU_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "YANTU_ALLOWED_ORIGINS": f"http://127.0.0.1:{port}",
        "YANTU_TLS_CERT": "",
        "YANTU_TLS_KEY": "",
        "YANTU_TLS_CA": "",
    }
    url = f"http://127.0.0.1:{port}"
    try:
        run("manage.py", "start", env=env)
        t = request(
            url,
            "/api/tasks",
            {
                "title": "隔离重启验收",
                "subject": "数学",
                "scheduled_date": "2026-10-17",
            },
        )
        run("manage.py", "stop", env=env)
        run("manage.py", "start", env=env)
        assert request(url, "/api/tasks")[0]["id"] == t["id"]
        assert "已运行" in run("manage.py", "start", env=env)
        backup = folder / "backup.zip"
        run("backup.py", "--output", str(backup), env=env)
        restored = folder / "restored"
        run("restore_archive.py", str(backup), "--output", str(restored), env=env)
        with sqlite3.connect(restored / "yantu.sqlite3") as c:
            assert c.execute("SELECT title FROM tasks").fetchone()[0] == "隔离重启验收"
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        run("manage.py", "stop", env=env)
        cert = folder / "tls"
        run("make_lan_cert.py", "127.0.0.1", "--output", str(cert), env=env)
        env.update(
            YANTU_TLS_CERT=str(cert / "server.crt"),
            YANTU_TLS_KEY=str(cert / "server.key"),
            YANTU_TLS_CA=str(cert / "ca.crt"),
            YANTU_ACCESS_TOKEN="isolated-test-token-only",
        )
        run("manage.py", "start", env=env)
        assert (
            request(
                f"https://127.0.0.1:{port}",
                "/api/tasks",
                token=env["YANTU_ACCESS_TOKEN"],
                ca=cert / "ca.crt",
            )[0]["id"]
            == t["id"]
        )
        assert "完整性：通过" in run("manage.py", "doctor", env=env)
        print(
            "真实进程验收通过：启动、重复启动、停止、重启持久化、完整备份、隔离恢复、证书校验、HTTPS 认证访问、诊断。全部使用临时数据和本机端口。"
        )
    finally:
        run("manage.py", "stop", env=env)
