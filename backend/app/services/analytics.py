"""Real database aggregates and explainable recommendations, no model required."""

from datetime import datetime, timedelta
from .study import local_date, day_start, segment_seconds
from ..db import rows


def analytics(conn, now, start, end):
    segments = conn.execute(
        "SELECT g.*,s.subject FROM study_segments g JOIN study_sessions s ON s.id=g.session_id"
    ).fetchall()

    # Compare dates in the application timezone, never by slicing UTC timestamps.
    event_days = {}
    for ev in conn.execute("SELECT * FROM activity_events"):
        day = local_date(datetime.fromisoformat(ev["happened_at"])).isoformat()
        event_days.setdefault(day, []).append(dict(ev))
    daily = []
    knowledge_names = {
        r["id"]: r["title"]
        for r in conn.execute("SELECT id,title FROM knowledge_points")
    }
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        daily.append(
            {
                "date": day.isoformat(),
                "seconds": int(
                    sum(
                        segment_seconds(
                            s["started_at"],
                            s["ended_at"],
                            now,
                            day_start(day),
                            day_start(day + timedelta(days=1)),
                        )
                        for s in segments
                    )
                ),
                "new_mistakes": sum(
                    e["kind"] == "mistake_created"
                    for e in event_days.get(day.isoformat(), [])
                ),
                "removed_mistakes": sum(
                    e["kind"] == "mistake_deleted"
                    for e in event_days.get(day.isoformat(), [])
                ),
                "mistake_total": sum(
                    (
                        1
                        if e["kind"] == "mistake_created"
                        else -1
                        if e["kind"] == "mistake_deleted"
                        else 0
                    )
                    for event_day, es in event_days.items()
                    if event_day <= day.isoformat()
                    for e in es
                ),
                "mastery_changes": sum(
                    e["kind"] == "knowledge_mastery"
                    for e in event_days.get(day.isoformat(), [])
                ),
            }
        )
    subjects = {}
    for s in segments:
        seconds = segment_seconds(
            s["started_at"],
            s["ended_at"],
            now,
            day_start(start),
            day_start(end + timedelta(days=1)),
        )
        if seconds:
            subjects[s["subject"]] = subjects.get(s["subject"], 0) + seconds
    task = dict(
        conn.execute(
            "SELECT COUNT(*) total,COALESCE(SUM(completed),0) completed FROM tasks WHERE scheduled_date BETWEEN ? AND ?",
            (str(start), str(end)),
        ).fetchone()
    )
    review_events = rows(
        conn.execute(
            "SELECT outcome,reviewed_at,due_date FROM review_events UNION ALL SELECT outcome,reviewed_at,due_date FROM knowledge_review_events"
        )
    )
    done = [
        r
        for r in review_events
        if start <= local_date(datetime.fromisoformat(r["reviewed_at"])) <= end
    ]
    scheduled_done = sum(
        bool(r["due_date"]) and str(start) <= r["due_date"] <= str(end)
        for r in review_events
    )
    pending = conn.execute(
        "SELECT COUNT(*) FROM (SELECT due_date FROM review_schedules UNION ALL SELECT due_date FROM knowledge_reviews) WHERE due_date BETWEEN ? AND ?",
        (str(start), str(end)),
    ).fetchone()[0]
    return {
        "start": str(start),
        "end": str(end),
        "data_source": "database",
        "seconds": sum(x["seconds"] for x in daily),
        "daily": daily,
        "subjects": [
            {"subject": k, "seconds": int(v)}
            for k, v in sorted(subjects.items(), key=lambda x: -x[1])
        ],
        "tasks": task,
        "reviews": {
            "completed": scheduled_done,
            "pending": pending,
            "attempts": len(done),
            "independent": sum(r["outcome"] == "remembered" for r in done),
            "failed": sum(r["outcome"] == "forgotten" for r in done),
        },
        "knowledge": rows(
            conn.execute(
                "SELECT mastery,COUNT(*) count FROM knowledge_points GROUP BY mastery ORDER BY mastery"
            )
        ),
        "mistakes": rows(
            conn.execute(
                "SELECT category,mastery,COUNT(*) count FROM mistakes GROUP BY category,mastery"
            )
        ),
        "mastery_history": [
            {**e, "title": knowledge_names.get(e["entity_id"], "已移除的知识点")}
            for day, es in event_days.items()
            if str(start) <= day <= str(end)
            for e in es
            if e["kind"] == "knowledge_mastery"
        ],
        "notes": "复习完成率按计划到期日在范围内的已完成次数与未完成安排计算；独立完成率按实际复习次数计算。历史掌握变化从启用 V2 后记录。",
    }


def recommendations(conn, now):
    today = local_date(now)
    report = analytics(conn, now, today - timedelta(days=27), today)
    weak = rows(
        conn.execute(
            "SELECT k.id,k.title,k.mastery,k.status,COUNT(mk.mistake_id) mistake_count FROM knowledge_points k LEFT JOIN mistake_knowledge mk ON mk.knowledge_id=k.id WHERE k.status!='unstarted' OR mk.mistake_id IS NOT NULL GROUP BY k.id ORDER BY k.mastery, mistake_count DESC LIMIT 10"
        )
    )
    due = conn.execute(
        "SELECT COUNT(*) FROM (SELECT due_date FROM review_schedules UNION ALL SELECT due_date FROM knowledge_reviews) WHERE due_date<=?",
        (str(today),),
    ).fetchone()[0]
    days = {d["date"] for d in report["daily"] if d["seconds"] > 0}
    # Continuity is lifetime history, not the 28-day reporting window.
    segments = conn.execute("SELECT started_at,ended_at FROM study_segments").fetchall()

    def studied_on(day):
        return (
            sum(
                segment_seconds(
                    s["started_at"],
                    s["ended_at"],
                    now,
                    day_start(day),
                    day_start(day + timedelta(days=1)),
                )
                for s in segments
            )
            >= 1
        )

    streak = 0
    cursor = today if studied_on(today) else today - timedelta(days=1)
    while studied_on(cursor):
        streak += 1
        cursor -= timedelta(days=1)
    recent = sum(d["seconds"] for d in report["daily"][-7:])
    previous = sum(d["seconds"] for d in report["daily"][-14:-7])
    daily = (
        [f"先处理 {due} 项到期复习，独立尝试后再查看答案。"]
        if due
        else ["今天没有到期复习；选择一个知识点，先独立完成基础题检验理解。"]
    )
    if weak:
        daily.append(
            f"优先巩固「{weak[0]['title']}」，当前掌握程度 {weak[0]['mastery']}/5，关联 {weak[0]['mistake_count']} 道错题。"
        )
    if report["reviews"]["failed"]:
        daily.append("近期仍有复习未掌握记录；先补前置定义与基本题，再增加题量。")
    weekly = [
        "为薄弱知识点安排短而明确的练习任务，并记录是否独立完成。",
        "周末复盘错误原因和复习结果，依据掌握变化调整下周任务。",
    ]
    return {
        "source": "rules",
        "label": "规则推荐 · 不是 AI 分析",
        "daily": daily,
        "weekly": weekly,
        "weak_points": weak,
        "summary": {
            "days_with_study": len(days),
            "streak_days": streak,
            "recent_week_seconds": recent,
            "previous_week_seconds": previous,
            "tasks": report["tasks"],
            "reviews": report["reviews"],
            "new_mistakes_28_days": sum(d["new_mistakes"] for d in report["daily"]),
        },
        "explanation": "优先级按低掌握程度、关联错题、复习失败和逾期安排；时长与连续性仅作为辅助。0–5 为个人记录或透明复习规则更新，不是考试成绩预测。",
    }
