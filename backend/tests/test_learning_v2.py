from datetime import timedelta
from test_mvp import task


def test_streak_uses_lifetime_history_and_stops_at_gap(client, clock):
    records = []
    for offset in range(35):
        result = client.post(
            "/api/records/manual",
            json={
                "subject": "数学",
                "minutes": 30,
                "started_at": (
                    clock().replace(hour=0) - timedelta(days=offset)
                ).isoformat(),
            },
        )
        assert result.status_code == 201, result.text
        records.append(result.json()["id"])
    summary = client.get("/api/recommendations").json()["summary"]
    assert summary["streak_days"] == 35
    assert summary["days_with_study"] == 28
    assert client.delete(f"/api/records/{records[30]}").status_code == 204
    assert client.get("/api/recommendations").json()["summary"]["streak_days"] == 30
    # Before today's first study, yesterday's continuity still counts.
    assert client.delete(f"/api/records/{records[0]}").status_code == 204
    assert client.get("/api/recommendations").json()["summary"]["streak_days"] == 29


def test_goals_priority_revision_and_subjects(client, clock):
    goal = client.post(
        "/api/goals",
        json={"title": "独立解题", "subject": "信号处理", "target_date": "2027-12-01"},
    ).json()
    data = {**task(), "goal_id": goal["id"], "priority": 1, "status": "doing"}
    t = client.post("/api/tasks", json=data).json()
    assert t["priority"] == 1 and t["status"] == "doing"
    assert client.get("/api/goals").json()[0]["task_count"] == 1
    assert any(s["name"] == "信号处理" for s in client.get("/api/subjects").json())
    assert (
        client.put(
            f"/api/tasks/{t['id']}", json={**data, "expected_revision": t["revision"]}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/tasks/{t['id']}", json={**data, "expected_revision": t["revision"]}
        ).status_code
        == 409
    )


def test_pomodoro_caps_after_closed_page_and_idempotent_start(client, clock):
    body = {
        "subject": "数学",
        "mode": "pomodoro",
        "target_minutes": 1,
        "request_id": "pomodoro-one",
    }
    s = client.post("/api/sessions", json=body).json()
    assert client.post("/api/sessions", json=body).json()["id"] == s["id"]
    clock.advance(seconds=20)
    client.post(f"/api/sessions/{s['id']}/pause")
    clock.advance(seconds=100)
    client.post(f"/api/sessions/{s['id']}/resume")
    clock.advance(seconds=100)
    assert client.get("/api/sessions/current").json() is None
    done = client.get("/api/sessions").json()[0]
    assert done["elapsed_seconds"] == 60
    assert client.get("/api/stats").json()["today_seconds"] == 60


def test_manual_record_overlap_and_statistics(client, clock):
    start = clock().replace(hour=0, minute=0, second=0)
    data = {
        "subject": "英语",
        "started_at": start.isoformat(),
        "minutes": 30,
        "topic": "阅读",
    }
    r = client.post("/api/records/manual", json=data)
    assert r.status_code == 201, r.text
    assert client.post("/api/records/manual", json=data).status_code == 409
    assert (
        client.post(
            "/api/records/manual",
            json={**data, "started_at": (clock() + timedelta(hours=1)).isoformat()},
        ).status_code
        == 422
    )
    out = client.get(
        "/api/analytics", params={"start": "2026-10-12", "end": "2026-10-18"}
    ).json()
    assert out["seconds"] == 1800 and out["subjects"][0]["subject"] == "英语"
    assert (
        client.put(
            f"/api/records/{r.json()['id']}", json={**data, "minutes": 20}
        ).status_code
        == 200
    )
    assert client.get("/api/stats").json()["today_seconds"] == 1200


def test_knowledge_tree_review_and_config(client, clock):
    base = {"title": "导数 V2", "domain": "微积分", "status": "learning", "mastery": 1}
    p = client.post("/api/knowledge", json=base).json()
    q = client.post(
        "/api/knowledge", json={**base, "title": "链式法则 V2", "parent_id": p["id"]}
    ).json()
    assert (
        client.put(
            f"/api/knowledge/{p['id']}", json={**base, "parent_id": q["id"]}
        ).status_code
        == 422
    )
    assert client.delete(f"/api/knowledge/{p['id']}").status_code == 409
    assert len(client.get("/api/knowledge-reviews").json()) == 2
    client.put(
        f"/api/review-schedule/knowledge/{p['id']}", json={"due_date": "2026-10-17"}
    )
    result = client.post(
        f"/api/knowledge/{p['id']}/review", json={"outcome": "remembered"}
    ).json()
    assert result["mastery"] == 2 and result["due_date"] == "2026-10-20"
    assert (
        client.post(
            f"/api/knowledge/{p['id']}/review", json={"outcome": "remembered"}
        ).status_code
        == 409
    )
    prefs = client.get("/api/settings").json()
    assert (
        client.put(
            "/api/settings", json={**prefs, "review_intervals": [1, 2, 4, 8, 16]}
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/settings", json={**prefs, "review_intervals": [1, 1, 4, 8, 16]}
        ).status_code
        == 422
    )
    assert client.get("/api/recommendations").json()["source"] == "rules"
