"""Shared validation and learning changes, always inside the caller's transaction."""

import json
from datetime import timedelta
from fastapi import HTTPException
from .settings import event, settings
from .study import local_date, timestamp


def row(conn, table, ident):
    found = conn.execute(f"SELECT * FROM {table} WHERE id=?", (ident,)).fetchone()
    if found is None:
        raise HTTPException(404, "记录不存在，可能已被删除。")
    return found


def check_revision(old, data):
    if data.expected_revision is not None and data.expected_revision != old["revision"]:
        raise HTTPException(409, "记录已在其他页面修改，请刷新后重新编辑。")


def extra(conn, table, ident, data, instant, new=False):
    fields = {
        "tasks": ["priority", "goal_id", "status"],
        "knowledge_points": [
            "subject",
            "parent_id",
            "mastery",
            "exam_scopes",
            "syllabus_source",
            "syllabus_year",
        ],
        "mistakes": ["wrong_answer", "category", "mastery"],
    }[table]
    values = {k: getattr(data, k) for k in fields if new or k in data.model_fields_set}
    if "exam_scopes" in values:
        values["exam_scopes"] = json.dumps(values["exam_scopes"])
    if table == "tasks":
        if values.get("goal_id"):
            row(conn, "goals", values["goal_id"])
        if data.completed:
            values["status"] = "done"
        elif values.get("status") == "done":
            conn.execute("UPDATE tasks SET completed=1 WHERE id=?", (ident,))
        else:
            values["status"] = values.get("status", "todo")
    if table == "knowledge_points":
        if values.get("parent_id"):
            parent = row(conn, table, values["parent_id"])
            if parent["subject"] != data.subject or parent["domain"] != data.domain:
                raise HTTPException(422, "子知识点必须与父知识点属于同一科目和章节。")
            visited = {ident}
            while parent:
                if parent["id"] in visited:
                    raise HTTPException(422, "知识层级不能形成循环。")
                visited.add(parent["id"])
                parent = (
                    row(conn, table, parent["parent_id"])
                    if parent["parent_id"]
                    else None
                )
        child = conn.execute(
            "SELECT 1 FROM knowledge_points WHERE parent_id=? AND (subject!=? OR domain!=?)",
            (ident, data.subject, data.domain),
        ).fetchone()
        if child:
            raise HTTPException(409, "请先调整子知识点的科目和章节。")
        if data.status != "unstarted":
            values["last_studied_at"] = timestamp(instant)
    if values:
        conn.execute(
            f"UPDATE {table} SET " + ",".join(k + "=?" for k in values) + " WHERE id=?",
            (*values.values(), ident),
        )
    if not new:
        conn.execute(f"UPDATE {table} SET revision=revision+1 WHERE id=?", (ident,))
    if hasattr(data, "subject"):
        conn.execute("INSERT OR IGNORE INTO subjects(name) VALUES (?)", (data.subject,))
    if table == "knowledge_points":
        current = row(conn, table, ident)
        event(conn, "knowledge_mastery", ident, current["mastery"], timestamp(instant))
        if current["status"] != "unstarted":
            ensure_knowledge_review(conn, ident, instant)
    elif table == "mistakes":
        if new or "mastery" in data.model_fields_set:
            schedule = conn.execute(
                "SELECT stage FROM review_schedules WHERE mistake_id=?", (ident,)
            ).fetchone()
            if data.mastery == "mastered":
                conn.execute(
                    "UPDATE review_schedules SET stage=5,due_date=NULL WHERE mistake_id=?",
                    (ident,),
                )
            elif schedule and schedule["stage"] == 5:
                conn.execute(
                    "UPDATE review_schedules SET stage=0,due_date=? WHERE mistake_id=?",
                    (
                        (
                            local_date(instant)
                            + timedelta(days=settings(conn).review_intervals[0])
                        ).isoformat(),
                        ident,
                    ),
                )
        if "file_ids" in data.model_fields_set or new:
            for fid in data.file_ids:
                file = row(conn, "files", fid)
                if file["kind"] != "image":
                    raise HTTPException(422, "错题只允许关联题目图片。")
            conn.execute("DELETE FROM mistake_files WHERE mistake_id=?", (ident,))
            conn.executemany(
                "INSERT INTO mistake_files VALUES (?,?)",
                [(ident, f) for f in sorted(set(data.file_ids))],
            )
        event(
            conn,
            "mistake_created" if new else "mistake_mastery",
            ident,
            int(data.mastery == "mastered"),
            timestamp(instant),
        )


def ensure_knowledge_review(conn, ident, instant):
    k = row(conn, "knowledge_points", ident)
    unresolved = conn.execute(
        "SELECT COUNT(*) FROM mistake_knowledge mk JOIN mistakes m ON m.id=mk.mistake_id WHERE mk.knowledge_id=? AND m.mastery!='mastered'",
        (ident,),
    ).fetchone()[0]
    delay = settings(conn).review_intervals[min(k["mastery"], 4)]
    if unresolved:
        delay = max(1, delay // (1 + unresolved))
    # Existing schedules are not postponed by editing notes or regenerating the queue.
    conn.execute(
        "INSERT OR IGNORE INTO knowledge_reviews(knowledge_id,due_date) VALUES (?,?)",
        (ident, (local_date(instant) + timedelta(days=delay)).isoformat()),
    )


def review_result(conn, old, outcome, instant):
    today = local_date(instant)
    if old["due_date"] is None or old["due_date"] > today.isoformat():
        raise HTTPException(409, "尚未到复习日期，或本轮复习已经完成。")
    stage = (
        min(5, old["stage"] + 1)
        if outcome == "remembered"
        else (old["stage"] if outcome == "assisted" else 0)
    )
    delay = (
        1 if outcome == "assisted" else settings(conn).review_intervals[min(stage, 4)]
    )
    due = (today + timedelta(days=delay)).isoformat() if stage < 5 else None
    return stage, due
