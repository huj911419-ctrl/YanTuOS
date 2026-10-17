from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Shanghai")
REVIEW_INTERVALS = (1, 3, 7, 14, 30)


def timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


def local_date(value: datetime):
    return value.astimezone(LOCAL_TZ).date()


def day_start(value):
    return datetime.combine(value, time.min, LOCAL_TZ)


def segment_seconds(
    start: str, end: str | None, now: datetime, window_start=None, window_end=None
):
    left = datetime.fromisoformat(start)
    right = min(datetime.fromisoformat(end) if end else now, now)
    if window_start:
        left = max(left, window_start)
    if window_end:
        right = min(right, window_end)
    return max(0.0, (right - left).total_seconds())


def session_view(conn, session, now):
    if not session:
        return None
    result = dict(session)
    segments = conn.execute(
        "SELECT * FROM study_segments WHERE session_id=? ORDER BY id", (result["id"],)
    ).fetchall()
    result["elapsed_seconds"] = int(
        sum(segment_seconds(s["started_at"], s["ended_at"], now) for s in segments)
    )
    result["server_now"] = timestamp(now)
    return result


def build_statistics(conn, now):
    today = local_date(now)
    week_start = today - timedelta(days=today.weekday())
    start_today = day_start(today)
    start_week = day_start(week_start)
    end_today = day_start(today + timedelta(days=1))
    segments = conn.execute(
        "SELECT g.started_at,g.ended_at,s.subject FROM study_segments g JOIN study_sessions s ON s.id=g.session_id"
    ).fetchall()
    today_seconds = 0.0
    week_seconds = 0.0
    by_subject = {}
    daily = []
    for segment in segments:
        today_seconds += segment_seconds(
            segment["started_at"], segment["ended_at"], now, start_today, end_today
        )
        seconds = segment_seconds(
            segment["started_at"], segment["ended_at"], now, start_week, end_today
        )
        week_seconds += seconds
        if seconds > 0:
            by_subject[segment["subject"]] = (
                by_subject.get(segment["subject"], 0) + seconds
            )
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        seconds = sum(
            segment_seconds(
                s["started_at"],
                s["ended_at"],
                now,
                day_start(day),
                day_start(day + timedelta(days=1)),
            )
            for s in segments
        )
        daily.append({"date": day.isoformat(), "seconds": int(seconds)})
    task_counts = dict(
        conn.execute(
            "SELECT COUNT(*) total, COALESCE(SUM(completed),0) completed FROM tasks WHERE scheduled_date=?",
            (today.isoformat(),),
        ).fetchone()
    )
    total_tasks = dict(
        conn.execute(
            "SELECT COUNT(*) total, COALESCE(SUM(completed),0) completed FROM tasks"
        ).fetchone()
    )
    return {
        "date": today.isoformat(),
        "timezone": str(LOCAL_TZ),
        "week_start": week_start.isoformat(),
        "today_seconds": int(today_seconds),
        "week_seconds": int(week_seconds),
        "subjects": [
            {"subject": subject, "seconds": int(seconds)}
            for subject, seconds in sorted(
                by_subject.items(), key=lambda item: -item[1]
            )
        ],
        "daily": daily,
        "today_tasks": task_counts,
        "all_tasks": total_tasks,
        "mistake_count": conn.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0],
        "due_review_count": conn.execute(
            "SELECT COUNT(*) FROM (SELECT due_date FROM review_schedules UNION ALL SELECT due_date FROM knowledge_reviews) WHERE due_date <= ?",
            (today.isoformat(),),
        ).fetchone()[0],
        "pending_review_count": conn.execute(
            "SELECT COUNT(*) FROM (SELECT due_date FROM review_schedules UNION ALL SELECT due_date FROM knowledge_reviews) WHERE due_date IS NOT NULL"
        ).fetchone()[0],
        "knowledge_count": conn.execute(
            "SELECT COUNT(*) FROM knowledge_points"
        ).fetchone()[0],
        "mastered_knowledge_count": conn.execute(
            "SELECT COUNT(*) FROM knowledge_points WHERE status='mastered'"
        ).fetchone()[0],
        "data_source": "database",
    }


def settle_timers(conn, now):
    """Lazily finish expired pomodoros at their exact deadline, even after a restart."""
    for session in conn.execute(
        "SELECT * FROM study_sessions WHERE status='running' AND mode='pomodoro'"
    ).fetchall():
        parts = conn.execute(
            "SELECT * FROM study_segments WHERE session_id=? ORDER BY id",
            (session["id"],),
        ).fetchall()
        used = 0.0
        for part in parts:
            start = datetime.fromisoformat(part["started_at"])
            remaining = max(0, session["target_seconds"] - used)
            if part["ended_at"]:
                used += max(
                    0,
                    (datetime.fromisoformat(part["ended_at"]) - start).total_seconds(),
                )
            elif now >= start + timedelta(seconds=remaining):
                end = timestamp(start + timedelta(seconds=remaining))
                conn.execute(
                    "UPDATE study_segments SET ended_at=? WHERE id=?", (end, part["id"])
                )
                conn.execute(
                    "UPDATE study_sessions SET status='finished',ended_at=? WHERE id=?",
                    (end, session["id"]),
                )
