from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
import logging
import uuid
import os
from pathlib import Path
import sqlite3
import tempfile

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .db import Database, rows, EXPORT_TABLES, SCHEMA_VERSION
from .services.learning import (
    extra,
    check_revision,
    ensure_knowledge_review,
    review_result,
)
from .services.settings import settings, event
from .routes.learning import router as learning_router
from .schemas import (
    KnowledgeInput,
    KnowledgeState,
    MistakeInput,
    ReviewInput,
    SessionFinish,
    SessionInput,
    TaskCompletion,
    TaskInput,
)
from .routes.ai import router as ai_router
from .routes.materials import router as materials_router
from .routes.data import router as data_router
from .services.auth import Auth
from .services.backup import recover_pending_restore
from .services.study import (
    build_statistics,
    local_date,
    session_view,
    timestamp,
    settle_timers,
)

ROOT = Path(__file__).resolve().parents[2]


def utc_now():
    return datetime.now(timezone.utc)


def require_row(conn, table, row_id):
    # Table names come only from the fixed names in this module.
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "记录不存在，可能已被删除。")
    return row


def mistake_view(conn, row):
    result = dict(row)
    schedule = conn.execute(
        "SELECT * FROM review_schedules WHERE mistake_id=?", (result["id"],)
    ).fetchone()
    result["review"] = dict(schedule)
    result["review_status"] = (
        "mastered"
        if schedule["stage"] == 5
        else ("new" if schedule["last_reviewed_at"] is None else "reviewing")
    )
    result["file_ids"] = [
        r[0]
        for r in conn.execute(
            "SELECT file_id FROM mistake_files WHERE mistake_id=?", (result["id"],)
        )
    ]
    result["knowledge_ids"] = [
        r[0]
        for r in conn.execute(
            "SELECT knowledge_id FROM mistake_knowledge WHERE mistake_id=? ORDER BY knowledge_id",
            (result["id"],),
        )
    ]
    return result


def validate_knowledge(conn, knowledge_ids):
    ids = sorted(set(knowledge_ids))
    if ids:
        count = conn.execute(
            f"SELECT COUNT(*) FROM knowledge_points WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        ).fetchone()[0]
        if count != len(ids):
            raise HTTPException(422, "关联知识点不存在，请刷新后重试。")
    return ids


def create_app(
    database_path: str | Path | None = None,
    clock=None,
    access_token=None,
    ai_transport=None,
):
    path = Path(
        database_path
        or os.getenv("YANTU_DATABASE_PATH", str(ROOT / "data/yantu.sqlite3"))
    )
    if not path.is_absolute():
        path = ROOT / path
    db = Database(path)
    now = clock or utc_now
    token = (
        os.getenv("YANTU_ACCESS_TOKEN", "") if access_token is None else access_token
    )
    auth = Auth(token, now)
    origins = set(
        os.getenv(
            "YANTU_ALLOWED_ORIGINS",
            "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
    )

    @asynccontextmanager
    async def lifespan(app):
        recover_pending_restore(db)
        db.initialize(timestamp(now()))
        yield

    app = FastAPI(
        title="研途 OS",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.db = db
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv(
            "YANTU_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver"
        ).split(","),
    )

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        if (
            request.url.path.startswith("/api/")
            and (db.path.parent / "restore-in-progress.json").exists()
        ):
            return JSONResponse(
                {
                    "detail": "数据恢复尚未完成，暂时拒绝读写。若恢复已中断，请停止并重新启动服务，程序将使用恢复前快照回滚。"
                },
                status_code=503,
            )
        if request.url.path.startswith("/api/"):
            public = request.url.path in (
                "/api/health",
                "/api/auth/login",
                "/api/auth/status",
            )
            if not public and not auth.authenticated(request):
                return JSONResponse(
                    {"detail": "请输入访问令牌后继续；未启用认证时仅允许本机访问。"},
                    status_code=401,
                )
            origin = request.headers.get("origin")
            if (
                request.method not in ("GET", "HEAD", "OPTIONS")
                and origin
                and origin not in origins
            ):
                return JSONResponse({"detail": "请求来源未获允许。"}, status_code=403)
            if request.headers.get(
                "sec-fetch-site"
            ) == "cross-site" and request.method not in ("GET", "HEAD", "OPTIONS"):
                return JSONResponse({"detail": "拒绝跨站修改请求。"}, status_code=403)
            length = request.headers.get("content-length", "0")
            if length.isdigit() and int(length) > 513 * 1024 * 1024:
                return JSONResponse({"detail": "请求体过大。"}, status_code=413)
        if request.url.path.startswith("/api/"):

            def settle():
                with db.transaction(write=True) as conn:
                    settle_timers(conn, now())

            await run_in_threadpool(settle)
        try:
            response = await call_next(request)
        except Exception as exc:
            ident = uuid.uuid4().hex[:12]
            logging.getLogger("yantu").error(
                "request_error id=%s type=%s path=%s",
                ident,
                type(exc).__name__,
                request.url.path,
            )
            response = JSONResponse(
                {"detail": f"服务遇到错误，请查看日志。编号：{ident}"}, status_code=500
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = (
            "no-store" if request.url.path.startswith("/api/") else "no-cache"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(
            {"detail": "数据存在冲突，请刷新后重试；同一分类的知识点名称不能重复。"},
            status_code=409,
        )

    app.include_router(learning_router(db, now))
    app.include_router(ai_router(db, now, ai_transport))
    app.include_router(materials_router(db, now))
    app.include_router(data_router(db, now))
    app.include_router(auth.router())

    @app.get("/api/health")
    def health():
        with db.transaction() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "version": "0.2.0", "timezone": "Asia/Shanghai"}

    @app.get("/api/tasks")
    def list_tasks(day: date | None = None):
        with db.transaction() as conn:
            if day:
                return rows(
                    conn.execute(
                        "SELECT * FROM tasks WHERE scheduled_date=? ORDER BY completed,id DESC",
                        (day.isoformat(),),
                    )
                )
            return rows(
                conn.execute("SELECT * FROM tasks ORDER BY scheduled_date DESC,id DESC")
            )

    @app.post("/api/tasks", status_code=201)
    def create_task(data: TaskInput):
        stamp = timestamp(now())
        with db.transaction(write=True) as conn:
            cursor = conn.execute(
                "INSERT INTO tasks(title,subject,scheduled_date,estimated_minutes,notes,completed,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    data.title,
                    data.subject,
                    data.scheduled_date.isoformat(),
                    data.estimated_minutes,
                    data.notes,
                    int(data.completed),
                    stamp,
                    stamp,
                ),
            )
            extra(conn, "tasks", cursor.lastrowid, data, now(), new=True)
            return dict(require_row(conn, "tasks", cursor.lastrowid))

    @app.put("/api/tasks/{task_id}")
    def update_task(task_id: int, data: TaskInput):
        with db.transaction(write=True) as conn:
            check_revision(require_row(conn, "tasks", task_id), data)
            conn.execute(
                "UPDATE tasks SET title=?,subject=?,scheduled_date=?,estimated_minutes=?,notes=?,completed=?,updated_at=? WHERE id=?",
                (
                    data.title,
                    data.subject,
                    data.scheduled_date.isoformat(),
                    data.estimated_minutes,
                    data.notes,
                    int(data.completed),
                    timestamp(now()),
                    task_id,
                ),
            )
            extra(conn, "tasks", task_id, data, now())
            return dict(require_row(conn, "tasks", task_id))

    @app.patch("/api/tasks/{task_id}/completion")
    def complete_task(task_id: int, data: TaskCompletion):
        with db.transaction(write=True) as conn:
            require_row(conn, "tasks", task_id)
            conn.execute(
                "UPDATE tasks SET completed=?,status=?,updated_at=?,revision=revision+1 WHERE id=?",
                (
                    int(data.completed),
                    "done" if data.completed else "todo",
                    timestamp(now()),
                    task_id,
                ),
            )
            return dict(require_row(conn, "tasks", task_id))

    @app.delete("/api/tasks/{task_id}", status_code=204)
    def delete_task(task_id: int):
        with db.transaction(write=True) as conn:
            require_row(conn, "tasks", task_id)
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    @app.get("/api/knowledge")
    def list_knowledge():
        with db.transaction() as conn:
            return rows(
                conn.execute(
                    "SELECT k.*, COUNT(mk.mistake_id) mistake_count, COALESCE(SUM(CASE WHEN r.stage < 5 THEN 1 ELSE 0 END),0) unresolved_count FROM knowledge_points k LEFT JOIN mistake_knowledge mk ON mk.knowledge_id=k.id LEFT JOIN review_schedules r ON r.mistake_id=mk.mistake_id GROUP BY k.id ORDER BY k.id"
                )
            )

    @app.post("/api/knowledge", status_code=201)
    def create_knowledge(data: KnowledgeInput):
        stamp = timestamp(now())
        with db.transaction(write=True) as conn:
            cursor = conn.execute(
                "INSERT INTO knowledge_points(title,domain,status,notes,created_at,updated_at,subject,parent_id) VALUES (?,?,?,?,?,?,?,?)",
                (
                    data.title,
                    data.domain,
                    data.status,
                    data.notes,
                    stamp,
                    stamp,
                    data.subject,
                    data.parent_id,
                ),
            )
            extra(conn, "knowledge_points", cursor.lastrowid, data, now(), new=True)
            return dict(require_row(conn, "knowledge_points", cursor.lastrowid))

    @app.put("/api/knowledge/{knowledge_id}")
    def update_knowledge(knowledge_id: int, data: KnowledgeInput):
        with db.transaction(write=True) as conn:
            check_revision(require_row(conn, "knowledge_points", knowledge_id), data)
            conn.execute(
                "UPDATE knowledge_points SET title=?,domain=?,status=?,notes=?,updated_at=?,subject=?,parent_id=? WHERE id=?",
                (
                    data.title,
                    data.domain,
                    data.status,
                    data.notes,
                    timestamp(now()),
                    data.subject,
                    data.parent_id,
                    knowledge_id,
                ),
            )
            extra(conn, "knowledge_points", knowledge_id, data, now())
            return dict(require_row(conn, "knowledge_points", knowledge_id))

    @app.patch("/api/knowledge/{knowledge_id}/status")
    def knowledge_status(knowledge_id: int, data: KnowledgeState):
        with db.transaction(write=True) as conn:
            require_row(conn, "knowledge_points", knowledge_id)
            conn.execute(
                "UPDATE knowledge_points SET status=?,updated_at=?,last_studied_at=?,revision=revision+1 WHERE id=?",
                (data.status, timestamp(now()), timestamp(now()), knowledge_id),
            )
            if data.status != "unstarted":
                ensure_knowledge_review(conn, knowledge_id, now())
            return dict(require_row(conn, "knowledge_points", knowledge_id))

    @app.delete("/api/knowledge/{knowledge_id}", status_code=204)
    def delete_knowledge(knowledge_id: int):
        with db.transaction(write=True) as conn:
            require_row(conn, "knowledge_points", knowledge_id)
            if conn.execute(
                "SELECT 1 FROM mistake_knowledge WHERE knowledge_id=?", (knowledge_id,)
            ).fetchone():
                raise HTTPException(409, "此知识点已关联错题，请先在错题中解除关联。")
            if conn.execute(
                "SELECT 1 FROM knowledge_points WHERE parent_id=? UNION ALL SELECT 1 FROM materials WHERE knowledge_id=?",
                (knowledge_id, knowledge_id),
            ).fetchone():
                raise HTTPException(
                    409, "此知识点仍有子知识点或学习资料，请先调整关联。"
                )
            conn.execute("DELETE FROM knowledge_points WHERE id=?", (knowledge_id,))

    @app.get("/api/sessions/current")
    def current_session():
        with db.transaction() as conn:
            return session_view(
                conn,
                conn.execute(
                    "SELECT * FROM study_sessions WHERE status != 'finished'"
                ).fetchone(),
                now(),
            )

    @app.get("/api/sessions")
    def session_history(day: date | None = None):
        with db.transaction() as conn:
            records = conn.execute(
                "SELECT * FROM study_sessions WHERE status='finished' ORDER BY started_at DESC"
            ).fetchall()
            if day:
                records = [
                    row
                    for row in records
                    if local_date(datetime.fromisoformat(row["started_at"])) == day
                ]
            return [session_view(conn, row, now()) for row in records]

    @app.post("/api/sessions", status_code=201)
    def start_session(data: SessionInput):
        instant = now()
        stamp = timestamp(instant)
        with db.transaction(write=True) as conn:
            if data.request_id:
                existing = conn.execute(
                    "SELECT * FROM study_sessions WHERE request_id=?",
                    (data.request_id,),
                ).fetchone()
                if existing:
                    return session_view(conn, existing, instant)
            if conn.execute(
                "SELECT 1 FROM study_sessions WHERE status != 'finished'"
            ).fetchone():
                raise HTTPException(409, "已有进行中的计时，请先结束。")
            cursor = conn.execute(
                "INSERT INTO study_sessions(subject,topic,started_at,status,mode,target_seconds,break_seconds,request_id) VALUES (?,?,?,'running',?,?,?,?)",
                (
                    data.subject,
                    data.topic,
                    stamp,
                    data.mode,
                    data.target_minutes * 60,
                    data.break_minutes * 60,
                    data.request_id,
                ),
            )
            sid = cursor.lastrowid
            conn.execute(
                "INSERT INTO study_segments(session_id,started_at) VALUES (?,?)",
                (sid, stamp),
            )
            return session_view(conn, require_row(conn, "study_sessions", sid), instant)

    def change_timer(session_id, action, notes=""):
        instant = now()
        stamp = timestamp(instant)
        with db.transaction(write=True) as conn:
            session = require_row(conn, "study_sessions", session_id)
            if session["status"] == "finished":
                if action == "finish":
                    return session_view(conn, session, instant)
                raise HTTPException(409, "这段学习已结束。")
            if action == "pause" and session["status"] == "running":
                conn.execute(
                    "UPDATE study_segments SET ended_at=MAX(started_at,?) WHERE session_id=? AND ended_at IS NULL",
                    (stamp, session_id),
                )
                conn.execute(
                    "UPDATE study_sessions SET status='paused' WHERE id=?",
                    (session_id,),
                )
            elif action == "resume" and session["status"] == "paused":
                conn.execute(
                    "INSERT INTO study_segments(session_id,started_at) VALUES (?,?)",
                    (session_id, stamp),
                )
                conn.execute(
                    "UPDATE study_sessions SET status='running' WHERE id=?",
                    (session_id,),
                )
            elif action == "finish":
                conn.execute(
                    "UPDATE study_segments SET ended_at=MAX(started_at,?) WHERE session_id=? AND ended_at IS NULL",
                    (stamp, session_id),
                )
                conn.execute(
                    "UPDATE study_sessions SET status='finished',ended_at=?,notes=? WHERE id=?",
                    (stamp, notes, session_id),
                )
            return session_view(
                conn, require_row(conn, "study_sessions", session_id), instant
            )

    @app.post("/api/sessions/{session_id}/pause")
    def pause(session_id: int):
        return change_timer(session_id, "pause")

    @app.post("/api/sessions/{session_id}/resume")
    def resume(session_id: int):
        return change_timer(session_id, "resume")

    @app.post("/api/sessions/{session_id}/finish")
    def finish(session_id: int, data: SessionFinish):
        return change_timer(session_id, "finish", data.notes)

    @app.get("/api/mistakes")
    def list_mistakes(
        knowledge_id: int | None = None, q: str = Query(default="", max_length=200)
    ):
        sql = "SELECT m.* FROM mistakes m WHERE 1=1"
        params = []
        if knowledge_id is not None:
            sql += " AND EXISTS (SELECT 1 FROM mistake_knowledge mk WHERE mk.mistake_id=m.id AND mk.knowledge_id=?)"
            params.append(knowledge_id)
        if q:
            sql += " AND (instr(m.title,?)>0 OR instr(m.question,?)>0 OR instr(m.error_reason,?)>0)"
            params.extend([q, q, q])
        with db.transaction() as conn:
            return [
                mistake_view(conn, row)
                for row in conn.execute(sql + " ORDER BY m.id DESC", params)
            ]

    @app.post("/api/mistakes", status_code=201)
    def create_mistake(data: MistakeInput):
        instant = now()
        stamp = timestamp(instant)
        with db.transaction(write=True) as conn:
            ids = validate_knowledge(conn, data.knowledge_ids)
            cursor = conn.execute(
                "INSERT INTO mistakes(title,subject,question,answer,error_reason,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    data.title,
                    data.subject,
                    data.question,
                    data.answer,
                    data.error_reason,
                    data.source,
                    stamp,
                    stamp,
                ),
            )
            mid = cursor.lastrowid
            conn.executemany(
                "INSERT INTO mistake_knowledge VALUES (?,?)",
                [(mid, kid) for kid in ids],
            )
            conn.execute(
                "INSERT INTO review_schedules(mistake_id,due_date) VALUES (?,?)",
                (
                    mid,
                    (
                        local_date(instant)
                        + timedelta(days=settings(conn).review_intervals[0])
                    ).isoformat(),
                ),
            )
            extra(conn, "mistakes", mid, data, instant, new=True)
            for kid in ids:
                ensure_knowledge_review(conn, kid, instant)
            return mistake_view(conn, require_row(conn, "mistakes", mid))

    @app.put("/api/mistakes/{mistake_id}")
    def update_mistake(mistake_id: int, data: MistakeInput):
        with db.transaction(write=True) as conn:
            check_revision(require_row(conn, "mistakes", mistake_id), data)
            ids = validate_knowledge(conn, data.knowledge_ids)
            conn.execute(
                "UPDATE mistakes SET title=?,subject=?,question=?,answer=?,error_reason=?,source=?,updated_at=? WHERE id=?",
                (
                    data.title,
                    data.subject,
                    data.question,
                    data.answer,
                    data.error_reason,
                    data.source,
                    timestamp(now()),
                    mistake_id,
                ),
            )
            conn.execute(
                "DELETE FROM mistake_knowledge WHERE mistake_id=?", (mistake_id,)
            )
            conn.executemany(
                "INSERT INTO mistake_knowledge VALUES (?,?)",
                [(mistake_id, kid) for kid in ids],
            )
            extra(conn, "mistakes", mistake_id, data, now())
            return mistake_view(conn, require_row(conn, "mistakes", mistake_id))

    @app.delete("/api/mistakes/{mistake_id}", status_code=204)
    def delete_mistake(mistake_id: int):
        with db.transaction(write=True) as conn:
            require_row(conn, "mistakes", mistake_id)
            event(conn, "mistake_deleted", mistake_id, 0, timestamp(now()))
            conn.execute("DELETE FROM mistakes WHERE id=?", (mistake_id,))

    @app.get("/api/reviews")
    def list_reviews(through: date | None = None):
        with db.transaction() as conn:
            sql = "SELECT m.* FROM mistakes m JOIN review_schedules r ON r.mistake_id=m.id WHERE r.due_date IS NOT NULL"
            params = []
            if through:
                sql += " AND r.due_date <= ?"
                params.append(through.isoformat())
            return [
                mistake_view(conn, row)
                for row in conn.execute(sql + " ORDER BY r.due_date,m.id", params)
            ]

    @app.get("/api/mistakes/{mistake_id}/reviews")
    def review_history(mistake_id: int):
        with db.transaction() as conn:
            require_row(conn, "mistakes", mistake_id)
            return rows(
                conn.execute(
                    "SELECT * FROM review_events WHERE mistake_id=? ORDER BY id DESC",
                    (mistake_id,),
                )
            )

    @app.post("/api/mistakes/{mistake_id}/review")
    def record_review(mistake_id: int, data: ReviewInput):
        instant = now()
        today = local_date(instant)
        with db.transaction(write=True) as conn:
            row = require_row(conn, "mistakes", mistake_id)
            old = conn.execute(
                "SELECT * FROM review_schedules WHERE mistake_id=?", (mistake_id,)
            ).fetchone()
            if old["due_date"] is None:
                raise HTTPException(409, "此题已完成本轮复习，可重新加入复习。")
            if date.fromisoformat(old["due_date"]) > today:
                raise HTTPException(
                    409, "尚未到复习日期；可查看答案，到期后再提交复习结果。"
                )
            stage, due = review_result(conn, old, data.outcome, instant)
            conn.execute(
                "UPDATE review_schedules SET stage=?,due_date=?,last_reviewed_at=? WHERE mistake_id=?",
                (stage, due, timestamp(instant), mistake_id),
            )
            conn.execute(
                "INSERT INTO review_events(mistake_id,outcome,reviewed_at,previous_stage,next_stage,next_due_date,notes,due_date) VALUES (?,?,?,?,?,?,?,?)",
                (
                    mistake_id,
                    data.outcome,
                    timestamp(instant),
                    old["stage"],
                    stage,
                    due,
                    data.notes,
                    old["due_date"],
                ),
            )
            mastery = (
                "mastered"
                if stage == 5
                else "reviewing"
                if data.outcome != "forgotten"
                else "unmastered"
            )
            conn.execute(
                "UPDATE mistakes SET mastery=?,updated_at=?,revision=revision+1 WHERE id=?",
                (mastery, timestamp(instant), mistake_id),
            )
            event(
                conn, "mistake_mastery", mistake_id, int(stage == 5), timestamp(instant)
            )
            row = require_row(conn, "mistakes", mistake_id)
            return mistake_view(conn, row)

    @app.post("/api/mistakes/{mistake_id}/restart-review")
    def restart_review(mistake_id: int):
        with db.transaction(write=True) as conn:
            row = require_row(conn, "mistakes", mistake_id)
            conn.execute(
                "UPDATE review_schedules SET stage=0,due_date=?,last_reviewed_at=NULL WHERE mistake_id=?",
                ((local_date(now()) + timedelta(days=1)).isoformat(), mistake_id),
            )
            return mistake_view(conn, row)

    @app.get("/api/stats")
    def statistics():
        with db.transaction() as conn:
            return build_statistics(conn, now())

    @app.get("/api/data/export")
    def export_json():
        with db.transaction() as conn:
            payload = {
                "format": "yantu-os",
                "schema_version": SCHEMA_VERSION,
                "exported_at": timestamp(now()),
                "timezone": "Asia/Shanghai",
                "tables": {
                    table: rows(conn.execute(f"SELECT * FROM {table}"))
                    for table in EXPORT_TABLES
                },
            }
        return JSONResponse(
            payload,
            headers={"Content-Disposition": 'attachment; filename="yantu-export.json"'},
        )

    @app.get("/api/data/backup")
    def backup_sqlite():
        fd, name = tempfile.mkstemp(prefix="yantu-", suffix=".sqlite3")
        os.close(fd)
        try:
            source = db.connect()
            destination = sqlite3.connect(name)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            return FileResponse(
                name,
                media_type="application/vnd.sqlite3",
                filename=f"yantu-{local_date(now())}.sqlite3",
                background=BackgroundTask(Path(name).unlink, missing_ok=True),
            )
        except Exception:
            Path(name).unlink(missing_ok=True)
            raise

    dist = ROOT / "frontend/dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend():
        if not (dist / "index.html").exists():
            return JSONResponse(
                {"detail": "前端尚未构建，请运行 ./scripts/build.sh"}, status_code=503
            )
        return FileResponse(dist / "index.html")

    @app.get("/{asset}", include_in_schema=False)
    def pwa_asset(asset: str):
        if asset not in (
            "sw.js",
            "manifest.webmanifest",
            "offline.html",
            "pwa-192.png",
            "pwa-512.png",
            "favicon.svg",
        ):
            raise HTTPException(404, "页面不存在。")
        target = dist / asset
        if not target.is_file():
            raise HTTPException(404, "请先构建前端。")
        return FileResponse(
            target, media_type="application/javascript" if asset == "sw.js" else None
        )

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        return FileResponse(ROOT / "frontend/public/favicon.svg")

    return app


app = create_app()
