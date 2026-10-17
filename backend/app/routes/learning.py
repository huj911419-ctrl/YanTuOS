from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import Field
from ..schemas import Input, ShortText, Subject, LongText, ReviewInput
from ..db import rows
from ..services.study import timestamp, session_view
from ..services.settings import SettingsInput, settings, save_settings, event
from ..services.learning import row, ensure_knowledge_review, review_result
from ..services.analytics import analytics, recommendations


class GoalInput(Input):
    title: ShortText
    subject: Subject = "数学"
    target_date: date
    notes: LongText = ""
    completed: bool = False


class SubjectInput(Input):
    name: Subject


class ScheduleInput(Input):
    due_date: date


class ManualSession(Input):
    subject: Subject
    topic: str = Field(default="", max_length=200)
    notes: LongText = ""
    started_at: datetime
    minutes: int = Field(ge=1, le=1440)


def router(db, now):
    api = APIRouter(prefix="/api")

    @api.get("/subjects")
    def subjects():
        with db.transaction() as c:
            return rows(c.execute("SELECT * FROM subjects ORDER BY id"))

    @api.post("/subjects", status_code=201)
    def create_subject(data: SubjectInput):
        with db.transaction(write=True) as c:
            cur = c.execute("INSERT INTO subjects(name) VALUES (?)", (data.name,))
            return dict(row(c, "subjects", cur.lastrowid))

    @api.delete("/subjects/{ident}", status_code=204)
    def delete_subject(ident: int):
        with db.transaction(write=True) as c:
            name = row(c, "subjects", ident)["name"]
            for table in (
                "tasks",
                "goals",
                "knowledge_points",
                "mistakes",
                "study_sessions",
            ):
                if c.execute(
                    f"SELECT 1 FROM {table} WHERE subject=?", (name,)
                ).fetchone():
                    raise HTTPException(409, "该科目仍有关联学习记录，请先调整记录。")
            c.execute("DELETE FROM subjects WHERE id=?", (ident,))

    @api.get("/goals")
    def goals():
        with db.transaction() as c:
            return rows(
                c.execute(
                    "SELECT g.*,COUNT(t.id) task_count,COALESCE(SUM(t.completed),0) completed_tasks FROM goals g LEFT JOIN tasks t ON t.goal_id=g.id GROUP BY g.id ORDER BY g.completed,g.target_date"
                )
            )

    @api.post("/goals", status_code=201)
    def create_goal(data: GoalInput):
        with db.transaction(write=True) as c:
            stamp = timestamp(now())
            cur = c.execute(
                "INSERT INTO goals(title,subject,target_date,notes,completed,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    data.title,
                    data.subject,
                    str(data.target_date),
                    data.notes,
                    int(data.completed),
                    stamp,
                    stamp,
                ),
            )
            c.execute(
                "INSERT OR IGNORE INTO subjects(name) VALUES (?)", (data.subject,)
            )
            return dict(row(c, "goals", cur.lastrowid))

    @api.put("/goals/{ident}")
    def update_goal(ident: int, data: GoalInput):
        with db.transaction(write=True) as c:
            row(c, "goals", ident)
            c.execute(
                "UPDATE goals SET title=?,subject=?,target_date=?,notes=?,completed=?,updated_at=? WHERE id=?",
                (
                    data.title,
                    data.subject,
                    str(data.target_date),
                    data.notes,
                    int(data.completed),
                    timestamp(now()),
                    ident,
                ),
            )
            return dict(row(c, "goals", ident))

    @api.delete("/goals/{ident}", status_code=204)
    def delete_goal(ident: int):
        with db.transaction(write=True) as c:
            row(c, "goals", ident)
            c.execute("DELETE FROM goals WHERE id=?", (ident,))

    def save_manual(c, data, ident=None):
        if data.started_at.tzinfo is None:
            raise HTTPException(422, "开始时间必须包含时区。")
        start = data.started_at.astimezone(timezone.utc)
        end = start + timedelta(minutes=data.minutes)
        if end > now():
            raise HTTPException(422, "补录不能包含未来时间。")
        if c.execute(
            "SELECT 1 FROM study_segments WHERE started_at<? AND COALESCE(ended_at,?)>? AND session_id!=?",
            (timestamp(end), timestamp(now()), timestamp(start), ident or -1),
        ).fetchone():
            raise HTTPException(409, "该时间段与已有学习记录重叠，请检查时间。")
        if ident:
            if row(c, "study_sessions", ident)["status"] != "finished":
                raise HTTPException(409, "请先结束计时再更正。")
            c.execute(
                "UPDATE study_sessions SET subject=?,topic=?,notes=?,started_at=?,ended_at=?,mode='manual' WHERE id=?",
                (
                    data.subject,
                    data.topic,
                    data.notes,
                    timestamp(start),
                    timestamp(end),
                    ident,
                ),
            )
            c.execute("DELETE FROM study_segments WHERE session_id=?", (ident,))
        else:
            ident = c.execute(
                "INSERT INTO study_sessions(subject,topic,notes,started_at,ended_at,status,mode) VALUES (?,?,?,?,?,'finished','manual')",
                (
                    data.subject,
                    data.topic,
                    data.notes,
                    timestamp(start),
                    timestamp(end),
                ),
            ).lastrowid
        c.execute(
            "INSERT INTO study_segments(session_id,started_at,ended_at) VALUES (?,?,?)",
            (ident, timestamp(start), timestamp(end)),
        )
        c.execute("INSERT OR IGNORE INTO subjects(name) VALUES (?)", (data.subject,))
        return session_view(c, row(c, "study_sessions", ident), now())

    @api.post("/records/manual", status_code=201)
    def manual(data: ManualSession):
        with db.transaction(write=True) as c:
            return save_manual(c, data)

    @api.put("/records/{ident}")
    def edit_record(ident: int, data: ManualSession):
        with db.transaction(write=True) as c:
            return save_manual(c, data, ident)

    @api.delete("/records/{ident}", status_code=204)
    def delete_record(ident: int):
        with db.transaction(write=True) as c:
            if row(c, "study_sessions", ident)["status"] != "finished":
                raise HTTPException(409, "请先结束计时。")
            c.execute("DELETE FROM study_sessions WHERE id=?", (ident,))

    @api.get("/settings")
    def get_settings():
        with db.transaction() as c:
            return settings(c).model_dump()

    @api.put("/settings")
    def put_settings(data: SettingsInput):
        with db.transaction(write=True) as c:
            save_settings(c, data)
            return data.model_dump()

    @api.get("/analytics")
    def stats(start: date, end: date):
        if end < start or (end - start).days > 366:
            raise HTTPException(422, "请选择不超过 367 天的有效日期范围。")
        with db.transaction() as c:
            return analytics(c, now(), start, end)

    @api.get("/recommendations")
    def recommend():
        with db.transaction() as c:
            return recommendations(c, now())

    @api.get("/knowledge-reviews")
    def knowledge_reviews():
        with db.transaction() as c:
            return rows(
                c.execute(
                    "SELECT k.*,r.stage,r.due_date FROM knowledge_reviews r JOIN knowledge_points k ON k.id=r.knowledge_id WHERE due_date IS NOT NULL ORDER BY due_date,k.mastery"
                )
            )

    @api.post("/knowledge-reviews/generate")
    def generate():
        with db.transaction(write=True) as c:
            for k in c.execute(
                "SELECT id FROM knowledge_points WHERE status!='unstarted' OR id IN(SELECT knowledge_id FROM mistake_knowledge)"
            ).fetchall():
                ensure_knowledge_review(c, k["id"], now())
        return {"ok": True}

    @api.post("/knowledge/{ident}/review")
    def knowledge_review(ident: int, data: ReviewInput):
        instant = now()
        with db.transaction(write=True) as c:
            k = row(c, "knowledge_points", ident)
            old = c.execute(
                "SELECT * FROM knowledge_reviews WHERE knowledge_id=?", (ident,)
            ).fetchone()
            if not old:
                raise HTTPException(409, "请先加入复习计划。")
            stage, due = review_result(c, old, data.outcome, instant)
            c.execute(
                "UPDATE knowledge_reviews SET stage=?,due_date=?,last_reviewed_at=? WHERE knowledge_id=?",
                (stage, due, timestamp(instant), ident),
            )
            c.execute(
                "INSERT INTO knowledge_review_events(knowledge_id,outcome,reviewed_at,previous_stage,next_stage,next_due_date,notes,due_date) VALUES (?,?,?,?,?,?,?,?)",
                (
                    ident,
                    data.outcome,
                    timestamp(instant),
                    old["stage"],
                    stage,
                    due,
                    data.notes,
                    old["due_date"],
                ),
            )
            mastery = max(
                0,
                min(
                    5,
                    k["mastery"]
                    + (
                        1
                        if data.outcome == "remembered"
                        else -1
                        if data.outcome == "forgotten"
                        else 0
                    ),
                ),
            )
            status = "mastered" if mastery == 5 else "consolidating"
            c.execute(
                "UPDATE knowledge_points SET mastery=?,status=?,last_reviewed_at=?,updated_at=?,revision=revision+1 WHERE id=?",
                (mastery, status, timestamp(instant), timestamp(instant), ident),
            )
            event(c, "knowledge_mastery", ident, mastery, timestamp(instant))
            return {"stage": stage, "due_date": due, "mastery": mastery}

    @api.get("/knowledge/{ident}/reviews")
    def knowledge_history(ident: int):
        with db.transaction() as c:
            return rows(
                c.execute(
                    "SELECT * FROM knowledge_review_events WHERE knowledge_id=? ORDER BY id DESC",
                    (ident,),
                )
            )

    @api.put("/review-schedule/{kind}/{ident}")
    def reschedule(kind: str, ident: int, data: ScheduleInput):
        if kind not in ("knowledge", "mistake"):
            raise HTTPException(404, "未知复习类型。")
        table, key, entity = (
            ("knowledge_reviews", "knowledge_id", "knowledge_points")
            if kind == "knowledge"
            else ("review_schedules", "mistake_id", "mistakes")
        )
        with db.transaction(write=True) as c:
            row(c, entity, ident)
            c.execute(
                f"INSERT INTO {table}({key},due_date) VALUES (?,?) ON CONFLICT({key}) DO UPDATE SET due_date=excluded.due_date,stage=CASE WHEN stage=5 THEN 0 ELSE stage END",
                (ident, str(data.due_date)),
            )
        return {"due_date": str(data.due_date)}

    return api
