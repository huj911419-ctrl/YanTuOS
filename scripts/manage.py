#!/usr/bin/env python3
"""Project-scoped lifecycle, with no shell evaluation or system service changes."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import ssl
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def load_env():
    path = ROOT / ".env"
    if not path.exists():
        return
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        key, sep, value = line.partition("=")
        if (
            not sep
            or not key.startswith("YANTU_")
            or not key.replace("_", "").isalnum()
        ):
            raise ValueError(f".env 第 {number} 行格式不正确；只允许 YANTU_ 配置。")
        values = shlex.split(value, comments=True)
        if len(values) > 1:
            raise ValueError(f".env 第 {number} 行含空格，请用引号括起值。")
        os.environ.setdefault(key, values[0] if values else "")


def options():
    host = os.getenv("YANTU_HOST", "127.0.0.1")
    port = int(os.getenv("YANTU_PORT", "8000"))
    if not 1024 <= port <= 65535:
        raise ValueError("端口必须在 1024–65535 范围。")
    cert = os.getenv("YANTU_TLS_CERT")
    key = os.getenv("YANTU_TLS_KEY")
    if bool(cert) != bool(key):
        raise ValueError("HTTPS 证书和私钥需同时配置。")
    if host not in ("127.0.0.1", "localhost", "::1"):
        address = ipaddress.ip_address(host)
        if not address.is_private or address.is_unspecified or address.is_multicast:
            raise ValueError(
                "只允许本机或明确的私有局域网 IP，不允许公网或全地址监听。"
            )
        if len(os.getenv("YANTU_ACCESS_TOKEN", "")) < 16:
            raise ValueError("局域网访问需要至少 16 字符的访问令牌。")
        if (
            not os.getenv("YANTU_ALLOWED_HOSTS")
            or "*" in os.getenv("YANTU_ALLOWED_HOSTS", "")
            or not os.getenv("YANTU_ALLOWED_ORIGINS")
        ):
            raise ValueError("请明确配置允许的主机与来源，不使用通配符。")
        if not cert:
            raise ValueError("局域网登录需要 HTTPS；先按 README 配置证书并在手机信任。")
    url = (
        ("https" if cert else "http")
        + "://"
        + (f"[{host}]" if ":" in host else host)
        + ":"
        + str(port)
    )
    return host, port, cert, key, url


def runtime():
    folder = Path(os.getenv("YANTU_RUNTIME_DIR", str(ROOT / ".runtime"))).resolve()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return folder


def process_start(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def owned(state):
    pid = state.get("pid")
    if not isinstance(pid, int) or process_start(pid) != state.get("start"):
        return False
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    return str(Path(__file__).resolve()).encode() in command and b"run" in command


def read_state():
    path = runtime() / "server.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def healthy(url):
    context = ssl.create_default_context(cafile=os.getenv("YANTU_TLS_CA") or None)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)
    )
    try:
        with opener.open(url + "/api/health", timeout=1) as response:
            return json.load(response).get("status") == "ok"
    except Exception:
        return False


def run():
    host, port, cert, key, _ = options()
    folder = runtime()
    (folder / "logs").mkdir(exist_ok=True, mode=0o700)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "backend"))
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}
        },
        "handlers": {
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(folder / "logs/server.log"),
                "maxBytes": 2_000_000,
                "backupCount": 5,
                "formatter": "standard",
                "encoding": "utf-8",
            }
        },
        "root": {"handlers": ["file"], "level": "INFO"},
        "loggers": {
            "uvicorn": {"handlers": ["file"], "level": "INFO", "propagate": False},
            "yantu": {"handlers": ["file"], "level": "INFO", "propagate": False},
        },
    }
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        workers=1,
        ssl_certfile=cert,
        ssl_keyfile=key,
        access_log=False,
        log_config=log_config,
    )


def start():
    state = read_state()
    if owned(state):
        print("研途 OS 已运行：" + state["url"])
        return
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise ValueError("前端尚未构建，请运行 ./scripts/build.sh。")
    host, port, cert, key, url = options()
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as exc:
            raise ValueError(
                "端口不可用；不会终止占用端口的其他程序。请检查 status/doctor 或更换 YANTU_PORT。"
            ) from exc
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "run"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    state = {
        "pid": proc.pid,
        "start": process_start(proc.pid),
        "url": url,
        "root": str(ROOT),
    }
    path = runtime() / "server.json"
    path.write_text(json.dumps(state))
    path.chmod(0o600)
    for _ in range(60):
        if proc.poll() is not None:
            raise ValueError("启动失败，请查看 " + str(runtime() / "logs/server.log"))
        if healthy(url):
            print("研途 OS 已启动：" + url)
            return
        time.sleep(0.25)
    raise ValueError(
        "进程已启动但健康检查未通过，请运行 doctor 并检查证书 CA 与日志；未强制终止进程。"
    )


def stop():
    state = read_state()
    path = runtime() / "server.json"
    if not owned(state):
        print("没有可确认归属的研途进程；未操作其他进程。")
        return
    os.kill(state["pid"], signal.SIGTERM)
    for _ in range(60):
        if not owned(state):
            path.unlink(missing_ok=True)
            print("研途 OS 已停止，数据保留。")
            return
        time.sleep(0.2)
    raise ValueError("进程仍在退出中，请查看日志；没有强制杀死进程。")


def doctor():
    state = read_state()
    print("项目：", ROOT)
    print("Python：", sys.version.split()[0])
    print("前端构建：", (ROOT / "frontend/dist/index.html").is_file())
    print("进程：", "运行" if owned(state) else "未运行")
    if owned(state):
        print("健康检查：", healthy(state["url"]))
        print("访问地址：", state["url"])
    print("日志：", runtime() / "logs/server.log")
    print("AI Key：", "已配置（不显示）" if os.getenv("YANTU_AI_API_KEY") else "未配置")
    db = Path(os.getenv("YANTU_DATABASE_PATH", str(ROOT / "data/yantu.sqlite3")))
    if not db.is_absolute():
        db = ROOT / db
    print("数据库：", db)
    if db.exists():
        sys.path.insert(0, str(ROOT / "backend"))
        from app.services.backup import validate_database, validate_files

        print("数据库版本：", validate_database(db))
        validate_files(db, db.parent / "uploads")
        print("完整性：通过")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "stop", "status", "doctor", "run"])
    args = parser.parse_args()
    try:
        load_env()
        if args.command == "status":
            state = read_state()
            print("运行中：" + state["url"] if owned(state) else "研途 OS 未运行")
        else:
            globals()[args.command]()
    except (ValueError, OSError) as exc:
        print("操作失败：" + str(exc), file=sys.stderr)
        sys.exit(1)
