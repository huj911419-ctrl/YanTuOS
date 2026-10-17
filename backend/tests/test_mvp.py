from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest
from app.main import create_app


def task(**kwargs):
    return {
        "title": "理解极限定义",
        "subject": "数学",
        "scheduled_date": "2026-10-17",
        "estimated_minutes": 30,
        **kwargs,
    }


def mistake(client, **kwargs):
    data = {
        "title": "极限计算",
        "subject": "数学",
        "question": "计算 lim sin(x)/x，x→0",
        "answer": "1",
        "error_reason": "不理解重要极限的适用条件",
        **kwargs,
    }
    response = client.post("/api/mistakes", json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_fresh_database_is_not_demo(client):
    assert client.get("/api/health").json()["status"] == "ok"
    for endpoint in ("tasks", "sessions", "mistakes", "reviews"):
        assert client.get(f"/api/{endpoint}").json() == []
    stats = client.get("/api/stats").json()
    assert stats["today_seconds"] == stats["week_seconds"] == 0
    assert stats["today_tasks"] == {"total": 0, "completed": 0}
    assert stats["mistake_count"] == stats["due_review_count"] == 0
    assert stats["data_source"] == "database"
    points = client.get("/api/knowledge").json()
    assert len(points) == 21
    assert all(p["is_reference"] and p["status"] == "unstarted" for p in points)


def test_task_complete_crud_and_date_filter(client):
    response = client.post("/api/tasks", json=task())
    assert response.status_code == 201
    tid = response.json()["id"]
    client.post("/api/tasks", json=task(title="明天任务", scheduled_date="2026-10-18"))
    assert [t["id"] for t in client.get("/api/tasks?day=2026-10-17").json()] == [tid]
    assert (
        client.put(
            f"/api/tasks/{tid}", json=task(title="独立完成 5 道题", notes="从基础开始")
        ).json()["title"]
        == "独立完成 5 道题"
    )
    assert (
        client.patch(f"/api/tasks/{tid}/completion", json={"completed": True}).json()[
            "completed"
        ]
        == 1
    )
    assert client.get("/api/stats").json()["today_tasks"] == {
        "total": 1,
        "completed": 1,
    }
    assert (
        client.patch(f"/api/tasks/{tid}/completion", json={"completed": False}).json()[
            "completed"
        ]
        == 0
    )
    assert client.delete(f"/api/tasks/{tid}").status_code == 204
    assert client.delete(f"/api/tasks/{tid}").status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"title": "   "},
        {"subject": ""},
        {"scheduled_date": "2026-02-30"},
        {"estimated_minutes": 0},
        {"estimated_minutes": 1441},
        {"title": "字" * 201},
        {"unexpected": True},
    ],
)
def test_task_validation(client, change):
    assert client.post("/api/tasks", json=task(**change)).status_code == 422
    assert client.get("/api/tasks").json() == []


def test_persistent_timer_pause_resume_and_idempotence(client, app, clock):
    result = client.post("/api/sessions", json={"subject": "数学", "topic": "极限入门"})
    assert result.status_code == 201
    sid = result.json()["id"]
    assert client.post("/api/sessions", json={"subject": "英语"}).status_code == 409
    clock.advance(seconds=60)
    assert client.post(f"/api/sessions/{sid}/pause").json()["elapsed_seconds"] == 60
    clock.advance(seconds=300)
    assert client.post(f"/api/sessions/{sid}/pause").json()["elapsed_seconds"] == 60
    # New app instance over the SAME file proves restart persistence.
    with TestClient(
        create_app(app.state.db.path, clock=clock, access_token="")
    ) as restarted:
        active = restarted.get("/api/sessions/current").json()
        assert (
            active["id"] == sid
            and active["status"] == "paused"
            and active["elapsed_seconds"] == 60
        )
        restarted.post(f"/api/sessions/{sid}/resume")
        restarted.post(f"/api/sessions/{sid}/resume")
        clock.advance(seconds=120)
        assert (
            restarted.post(
                f"/api/sessions/{sid}/finish", json={"notes": "理解了定义"}
            ).json()["elapsed_seconds"]
            == 180
        )
        assert (
            restarted.post(
                f"/api/sessions/{sid}/finish", json={"notes": "重试"}
            ).json()["notes"]
            == "理解了定义"
        )
        assert restarted.post(f"/api/sessions/{sid}/resume").status_code == 409
        assert restarted.get("/api/sessions/current").json() is None
        history = restarted.get("/api/sessions?day=2026-10-17").json()
        assert len(history) == 1 and history[0]["elapsed_seconds"] == 180
        stats = restarted.get("/api/stats").json()
        assert stats["today_seconds"] == stats["week_seconds"] == 180
        assert stats["subjects"] == [{"subject": "数学", "seconds": 180}]
        assert len(restarted.get("/api/knowledge").json()) == 21


def test_running_statistics_and_subject_aggregation(client, clock):
    sid = client.post("/api/sessions", json={"subject": "数学"}).json()["id"]
    clock.advance(seconds=90)
    assert client.get("/api/stats").json()["today_seconds"] == 90
    client.post(f"/api/sessions/{sid}/finish", json={})
    sid = client.post("/api/sessions", json={"subject": "英语"}).json()["id"]
    clock.advance(seconds=60)
    client.post(f"/api/sessions/{sid}/finish", json={})
    stats = client.get("/api/stats").json()
    assert stats["subjects"] == [
        {"subject": "数学", "seconds": 90},
        {"subject": "英语", "seconds": 60},
    ]
    assert stats["today_seconds"] == 150


def test_timer_crosses_shanghai_midnight_and_week_boundary(client, clock):
    # Sunday 23:59:30 Asia/Shanghai -> Monday 00:01:00.
    clock.value = datetime(2026, 10, 18, 15, 59, 30, tzinfo=timezone.utc)
    sid = client.post("/api/sessions", json={"subject": "数学"}).json()["id"]
    clock.advance(seconds=90)
    client.post(f"/api/sessions/{sid}/finish", json={})
    stats = client.get("/api/stats").json()
    assert stats["date"] == "2026-10-19" and stats["week_start"] == "2026-10-19"
    assert stats["today_seconds"] == stats["week_seconds"] == 60
    assert stats["daily"][0]["seconds"] == 60
    assert client.get("/api/sessions").json()[0]["elapsed_seconds"] == 90


def test_timer_cannot_start_twice_concurrently(client):
    def start(_):
        return client.post("/api/sessions", json={"subject": "数学"}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(start, range(2))) == [201, 409]


def test_knowledge_crud_and_conflicts(client):
    data = {"title": "自定义练习", "domain": "基础工具", "notes": "可扩展"}
    response = client.post("/api/knowledge", json=data)
    assert response.status_code == 201
    kid = response.json()["id"]
    assert client.post("/api/knowledge", json=data).status_code == 409
    assert (
        client.patch(
            f"/api/knowledge/{kid}/status", json={"status": "mastered"}
        ).json()["status"]
        == "mastered"
    )
    assert client.get("/api/stats").json()["mastered_knowledge_count"] == 1
    assert (
        client.put(
            f"/api/knowledge/{kid}",
            json={**data, "title": "已编辑", "status": "learning"},
        ).json()["title"]
        == "已编辑"
    )
    assert (
        client.patch(
            f"/api/knowledge/{kid}/status", json={"status": "fake"}
        ).status_code
        == 422
    )
    assert client.delete(f"/api/knowledge/{kid}").status_code == 204


def test_mistake_crud_search_knowledge_and_referential_integrity(client):
    kid = client.get("/api/knowledge").json()[0]["id"]
    m = mistake(client, knowledge_ids=[kid, kid])
    assert m["knowledge_ids"] == [kid]
    assert m["review"]["due_date"] == "2026-10-18" and m["review_status"] == "new"
    assert len(client.get(f"/api/mistakes?knowledge_id={kid}").json()) == 1
    assert client.get("/api/mistakes?knowledge_id=999999").json() == []
    assert len(client.get("/api/mistakes", params={"q": "重要极限"}).json()) == 1
    assert client.get("/api/mistakes", params={"q": "' OR 1=1 --"}).json() == []
    assert client.delete(f"/api/knowledge/{kid}").status_code == 409
    points = client.get("/api/knowledge").json()
    assert next(p for p in points if p["id"] == kid)["unresolved_count"] == 1
    response = client.put(
        f"/api/mistakes/{m['id']}",
        json={"title": "更新", "question": "新题目", "knowledge_ids": []},
    )
    assert (
        response.status_code == 200
        and response.json()["review"]["due_date"] == "2026-10-18"
    )
    assert client.delete(f"/api/knowledge/{kid}").status_code == 204
    assert client.delete(f"/api/mistakes/{m['id']}").status_code == 204
    assert client.get("/api/reviews").json() == []


def test_bad_knowledge_reference_rolls_back_entire_mistake(client):
    response = client.post(
        "/api/mistakes",
        json={"title": "test", "question": "test", "knowledge_ids": [999999]},
    )
    assert response.status_code == 422
    assert client.get("/api/mistakes").json() == []
    assert client.get("/api/reviews").json() == []


def test_full_review_schedule_and_fail_reset(client, clock):
    m = mistake(client)
    mid = m["id"]
    endpoint = f"/api/mistakes/{mid}/review"
    assert client.get("/api/reviews?through=2026-10-17").json() == []
    assert client.post(endpoint, json={"outcome": "remembered"}).status_code == 409
    clock.advance(days=1)
    assert client.get("/api/stats").json()["due_review_count"] == 1
    response = client.post(
        endpoint, json={"outcome": "forgotten", "notes": "再看定义"}
    ).json()
    assert (
        response["review"]["stage"] == 0
        and response["review"]["due_date"] == "2026-10-19"
    )
    clock.advance(days=1)
    for stage, wait in enumerate([3, 7, 14, 30, None], start=1):
        result = client.post(endpoint, json={"outcome": "remembered"})
        assert result.status_code == 200
        schedule = result.json()["review"]
        assert schedule["stage"] == stage
        if wait:
            assert schedule["due_date"] is not None
            # No same-day double counting from a second click.
            assert (
                client.post(endpoint, json={"outcome": "remembered"}).status_code == 409
            )
            clock.advance(days=wait)
            assert (
                schedule["due_date"]
                == clock.value.astimezone(
                    __import__("zoneinfo").ZoneInfo("Asia/Shanghai")
                )
                .date()
                .isoformat()
            )
        else:
            assert schedule["due_date"] is None
            assert result.json()["review_status"] == "mastered"
    assert client.get("/api/stats").json()["pending_review_count"] == 0
    history = client.get(f"/api/mistakes/{mid}/reviews").json()
    assert len(history) == 6 and history[-1]["notes"] == "再看定义"
    assert (
        client.post(f"/api/mistakes/{mid}/restart-review").json()["review"]["stage"]
        == 0
    )
    assert client.get("/api/stats").json()["pending_review_count"] == 1


def test_overdue_review_reschedules_from_actual_review_date(client, clock):
    m = mistake(client)
    clock.advance(days=9)
    result = client.post(
        f"/api/mistakes/{m['id']}/review", json={"outcome": "remembered"}
    ).json()
    assert result["review"]["due_date"] == "2026-10-29"


def test_export_backup_restore_and_persistence(client, app, tmp_path, clock):
    client.post("/api/tasks", json=task())
    m = mistake(client)
    sid = client.post("/api/sessions", json={"subject": "数学"}).json()["id"]
    clock.advance(seconds=30)
    client.post(f"/api/sessions/{sid}/pause")
    exported = client.get("/api/data/export").json()
    assert exported["format"] == "yantu-os" and exported["schema_version"] == 3
    assert len(exported["tables"]["tasks"]) == len(exported["tables"]["mistakes"]) == 1
    backup = client.get("/api/data/backup")
    assert backup.status_code == 200 and backup.content.startswith(b"SQLite format 3")
    original = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    original.write_bytes(backup.content)
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts/restore.py"
    result = subprocess.run(
        [sys.executable, str(script), str(original), "--output", str(restored)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (
        subprocess.run(
            [sys.executable, str(script), str(original), "--output", str(restored)],
            capture_output=True,
        ).returncode
        == 1
    )
    with TestClient(create_app(restored, clock=clock, access_token="")) as recovered:
        assert recovered.get("/api/data/export").json()["tables"] == exported["tables"]
        assert recovered.get("/api/sessions/current").json()["status"] == "paused"
        assert recovered.get("/api/sessions/current").json()["elapsed_seconds"] == 30
        assert recovered.get("/api/mistakes").json()[0]["id"] == m["id"]
    bad = tmp_path / "not-a-backup.sqlite3"
    with sqlite3.connect(bad) as conn:
        conn.execute("CREATE TABLE unrelated(x)")
    output = tmp_path / "refused.sqlite3"
    assert (
        subprocess.run(
            [sys.executable, str(script), str(bad), "--output", str(output)],
            capture_output=True,
        ).returncode
        == 1
    )
    assert not output.exists()


def test_ai_is_explicitly_unavailable(client):
    assert client.get("/api/ai/status").json()["available"] is False
    response = client.post("/api/ai/explain", json={"question": "什么是极限？"})
    assert response.status_code == 503
    assert "尚未接入" in response.json()["detail"]


def test_origin_and_host_guard(client):
    assert (
        client.post(
            "/api/tasks", json=task(), headers={"Origin": "https://untrusted.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/tasks", json=task(), headers={"Origin": "http://127.0.0.1:8000"}
        ).status_code
        == 201
    )
    assert (
        client.get("/api/stats", headers={"Host": "untrusted.example"}).status_code
        == 400
    )
    assert client.get("/api/stats").headers["cache-control"] == "no-store"


def test_optional_token_protects_personal_data(tmp_path):
    app = create_app(tmp_path / "protected.sqlite3", access_token="test-token-only")
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        for path in (
            "/api/tasks",
            "/api/stats",
            "/api/data/export",
            "/api/data/backup",
        ):
            assert client.get(path).status_code == 401
            assert (
                client.get(path, headers={"Authorization": "Bearer wrong"}).status_code
                == 401
            )
            assert (
                client.get(
                    path, headers={"Authorization": "Bearer test-token-only"}
                ).status_code
                == 200
            )


@pytest.mark.parametrize(
    "path", ["/api/tasks/99999", "/api/knowledge/99999", "/api/mistakes/99999"]
)
def test_delete_unknown_records_is_404(client, path):
    assert client.delete(path).status_code == 404
