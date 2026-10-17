import io
import json
import sqlite3
import zipfile
from pathlib import Path
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.backup import prepare_restore
from test_mvp import task


def image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_files_materials_and_exports(client):
    picture = client.post(
        "/api/files?kind=image",
        files={"file": ("题目.png", image_bytes(), "image/png")},
    )
    assert picture.status_code == 201, picture.text
    ident = picture.json()["id"]
    assert (
        client.post(
            "/api/files?kind=image",
            files={"file": ("evil.svg", b"<svg/>", "image/svg+xml")},
        ).status_code
        == 422
    )
    assert client.get("/api/files/" + ident).content == image_bytes()
    m = client.post(
        "/api/mistakes",
        json={
            "title": "图片题",
            "question": "见图片",
            "file_ids": [ident],
            "wrong_answer": "3",
            "category": "计算",
        },
    ).json()
    assert m["file_ids"] == [ident] and m["wrong_answer"] == "3"
    assert client.delete("/api/files/" + ident).status_code == 409
    assert "图片题" in client.get("/api/mistakes-export").text
    f = client.post(
        "/api/files",
        files={
            "file": ("笔记.md", "# 我的理解\n导数描述变化率".encode(), "text/plain")
        },
    ).json()
    material = client.post(
        "/api/materials",
        json={"title": "导数笔记", "file_id": f["id"], "notes": "需要练习"},
    ).json()
    assert (
        material["extraction_status"] == "text"
        and "变化率" in material["extracted_text"]
    )
    assert len(client.get("/api/materials?q=导数").json()) == 1
    assert "变化率" in client.get(f"/api/materials/{material['id']}/export").text
    assert client.delete(f"/api/materials/{material['id']}").status_code == 204
    assert client.delete("/api/files/" + f["id"]).status_code == 204


def test_full_archive_isolated_restore_and_live_confirm(client, tmp_path, clock):
    t = client.post("/api/tasks", json=task()).json()
    file = client.post(
        "/api/files?kind=image", files={"file": ("题.png", image_bytes(), "image/png")}
    ).json()
    client.post(
        "/api/mistakes",
        json={"title": "需图片", "question": "图片题", "file_ids": [file["id"]]},
    )
    archive = client.get("/api/data/archive")
    assert archive.status_code == 200, (
        archive.text[:200] if archive.status_code != 200 else ""
    )
    source = tmp_path / "full.zip"
    source.write_bytes(archive.content)
    summary = prepare_restore(source, tmp_path / "isolated")
    assert summary["counts"]["tasks"] == 1 and summary["counts"]["files"] == 1
    with TestClient(
        create_app(tmp_path / "isolated/yantu.sqlite3", clock=clock, access_token="")
    ) as restored:
        assert restored.get("/api/tasks").json()[0]["id"] == t["id"]
        assert restored.get("/api/files/" + file["id"]).content == image_bytes()
        assert restored.get("/api/data/integrity").json()["integrity"] == "ok"
    client.post("/api/tasks", json={**task(), "title": "备份后的新记录"})
    preview = client.post(
        "/api/data/restore/preview",
        files={"file": ("full.zip", archive.content, "application/zip")},
    )
    assert preview.status_code == 200, preview.text
    stage = preview.json()["stage_id"]
    assert (
        client.post(
            "/api/data/restore/confirm", json={"stage_id": stage, "confirmation": "yes"}
        ).status_code
        == 422
    )
    result = client.post(
        "/api/data/restore/confirm",
        json={"stage_id": stage, "confirmation": "覆盖当前学习数据"},
    )
    assert result.status_code == 200, result.text
    assert Path(result.json()["rollback_backup"]).is_file()
    assert len(client.get("/api/tasks").json()) == 1
    assert client.get("/api/data/integrity").status_code == 200


def test_json_import_and_malicious_archive_rejected(client, tmp_path):
    client.post("/api/tasks", json=task())
    payload = client.get("/api/data/export").content
    preview = client.post(
        "/api/data/restore/preview",
        files={"file": ("export.json", payload, "application/json")},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["counts"]["tasks"] == 1
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as z:
        z.writestr("../escape", "secret")
        z.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": "yantu-os-backup",
                    "version": 1,
                    "sha256": {"../escape": "bad", "database.sqlite3": "bad"},
                }
            ),
        )
        z.writestr("database.sqlite3", "broken")
    response = client.post(
        "/api/data/restore/preview",
        files={"file": ("attack.zip", content.getvalue(), "application/zip")},
    )
    assert response.status_code == 422
    assert len(client.get("/api/tasks").json()) == 1
    assert not (tmp_path / "escape").exists()


def test_migration_from_v1_preserves_data_and_relations(tmp_path, clock):
    path = tmp_path / "old.sqlite3"
    c = sqlite3.connect(path)
    c.executescript(
        (Path(__file__).parents[1] / "app/migrations/001_initial.sql").read_text()
    )
    c.execute(
        "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL)"
    )
    c.execute("INSERT INTO schema_migrations VALUES(1,?)", (clock().isoformat(),))
    c.execute(
        "INSERT INTO knowledge_points(id,title,domain,created_at,updated_at) VALUES(17,'公式','第一章',?,?)",
        (clock().isoformat(), clock().isoformat()),
    )
    c.execute(
        "INSERT INTO mistakes(id,title,question,created_at,updated_at) VALUES(5,'旧错题','题目',?,?)",
        (clock().isoformat(), clock().isoformat()),
    )
    c.execute("INSERT INTO mistake_knowledge VALUES(5,17)")
    c.execute(
        "INSERT INTO review_schedules(mistake_id,due_date) VALUES(5,'2026-10-18')"
    )
    c.commit()
    c.close()
    with TestClient(create_app(path, clock=clock, access_token="")) as app:
        assert app.get("/api/mistakes").json()[0]["knowledge_ids"] == [17]
        assert app.get("/api/knowledge").json()[0]["id"] == 17
        assert (
            app.post(
                "/api/knowledge",
                json={"title": "公式", "domain": "第一章", "subject": "物理"},
            ).status_code
            == 201
        )
        assert app.get("/api/data/integrity").status_code == 200
    assert list((tmp_path / "backups").glob("pre-migration*.sqlite3"))


def test_cookie_auth_expiry_csrf_and_rate_limit(tmp_path, clock):
    app = create_app(
        tmp_path / "auth.sqlite3", clock=clock, access_token="test-only-long-token"
    )
    with TestClient(app, base_url="https://localhost") as c:
        assert c.get("/api/tasks").status_code == 401
        login = c.post("/api/auth/login", json={"token": "test-only-long-token"})
        assert (
            login.status_code == 200
            and "HttpOnly" in login.headers["set-cookie"]
            and "Secure" in login.headers["set-cookie"]
        )
        assert c.get("/api/tasks").status_code == 200
        assert (
            c.post(
                "/api/tasks", json=task(), headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        clock.advance(hours=25)
        assert c.get("/api/tasks").status_code == 401
        for _ in range(10):
            assert c.post("/api/auth/login", json={"token": "wrong"}).status_code == 401
        assert c.post("/api/auth/login", json={"token": "wrong"}).status_code == 429


def model_client(tmp_path, clock, monkeypatch, handler):
    monkeypatch.setenv("YANTU_AI_API_KEY", "test-only-not-real")
    monkeypatch.setenv("YANTU_AI_BASE_URL", "https://controlled.invalid/v1")
    monkeypatch.setenv("YANTU_AI_MODEL", "controlled-test-model")
    return TestClient(
        create_app(
            tmp_path / "ai.sqlite3",
            clock=clock,
            access_token="",
            ai_transport=httpx.MockTransport(handler),
        )
    )


def test_model_consent_context_and_history(tmp_path, clock, monkeypatch):
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-only-not-real"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "受控测试模型回复；不是线上模型。"}}
                ]
            },
        )

    with model_client(tmp_path, clock, monkeypatch, handler) as c:
        k = c.post(
            "/api/knowledge", json={"title": "授权知识", "notes": "选中才发送"}
        ).json()
        body = {"prompt": "解释导数", "purpose": "concept", "knowledge_ids": [k["id"]]}
        assert c.post("/api/ai/chat", json=body).status_code == 409 and not calls
        preview = c.post("/api/ai/preview", json=body).json()
        assert "选中才发送" in json.dumps(preview, ensure_ascii=False)
        assert "test-only-not-real" not in json.dumps(preview)
        result = c.post(
            "/api/ai/chat",
            json={**body, "consent": True, "approved_digest": preview["digest"]},
        )
        assert result.status_code == 200, result.text
        assert len(calls) == 1 and result.json()["source"] == "model"
        assert len(c.get("/api/ai/history").json()) == 1
        assert (
            c.post(
                "/api/ai/chat",
                json={
                    **body,
                    "prompt": "改变内容",
                    "consent": True,
                    "approved_digest": preview["digest"],
                },
            ).status_code
            == 409
        )
        assert "test-only-not-real" not in c.get("/api/data/export").text


@pytest.mark.parametrize(
    "failure,expected",
    [(401, 502), (429, 503), (500, 502), ("bad", 502), ("timeout", 504)],
)
def test_model_failures_never_fabricate_answer(
    tmp_path, clock, monkeypatch, failure, expected
):
    calls = []

    def handler(request):
        calls.append(1)
        if failure == "timeout":
            raise httpx.ReadTimeout("controlled timeout")
        if failure == "bad":
            return httpx.Response(200, json={"wrong": "format"})
        return httpx.Response(failure, json={"error": "controlled failure"})

    with model_client(tmp_path, clock, monkeypatch, handler) as c:
        body = {"prompt": "测试"}
        p = c.post("/api/ai/preview", json=body).json()
        r = c.post(
            "/api/ai/chat",
            json={**body, "consent": True, "approved_digest": p["digest"]},
        )
        assert r.status_code == expected and len(calls) == 1
        assert c.get("/api/ai/history").json() == []


def test_local_math_is_bounded_and_does_not_execute(client):
    assert (
        client.post("/api/ai/verify-math", json={"expression": "(2+3)*4=20"}).json()[
            "equal"
        ]
        is True
    )
    for expression in [
        "__import__('os').getcwd()",
        "2**1000000",
        "1/0",
        "(1).__class__",
    ]:
        assert (
            client.post(
                "/api/ai/verify-math", json={"expression": expression}
            ).status_code
            == 422
        )


def test_pdf_text_layer_and_scanned_status_are_truthful(client):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 100 Td (Derivative notes) Tj ET")
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    content = io.BytesIO()
    writer.write(content)
    f = client.post(
        "/api/files",
        files={"file": ("notes.pdf", content.getvalue(), "application/pdf")},
    ).json()
    m = client.post(
        "/api/materials", json={"title": "PDF 验证", "file_id": f["id"]}
    ).json()
    assert m["extraction_status"] == "text" and "Derivative" in m["extracted_text"]
    blank = PdfWriter()
    blank.add_blank_page(width=200, height=200)
    content = io.BytesIO()
    blank.write(content)
    f = client.post(
        "/api/files",
        files={"file": ("scan.pdf", content.getvalue(), "application/pdf")},
    ).json()
    m = client.post(
        "/api/materials", json={"title": "无文本层", "file_id": f["id"]}
    ).json()
    assert m["extraction_status"] == "no_text_layer" and m["extracted_text"] == ""


def test_restore_failure_rolls_back_and_keeps_snapshot(
    client, app, tmp_path, monkeypatch
):
    import app.services.backup as service

    client.post("/api/tasks", json=task())
    source = tmp_path / "saved.zip"
    source.write_bytes(client.get("/api/data/archive").content)
    prepare_restore(source, tmp_path / "candidate")
    client.post("/api/tasks", json={**task(), "title": "恢复前的重要记录"})
    original = service.copy_database
    calls = []

    def fail_once(source, target):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("controlled failure")
        return original(source, target)

    monkeypatch.setattr(service, "copy_database", fail_once)
    with pytest.raises(OSError):
        service.activate_restore(app.state.db, tmp_path / "candidate")
    assert len(client.get("/api/tasks").json()) == 2
    assert not (app.state.db.path.parent / "restore-in-progress.json").exists()
    assert list((app.state.db.path.parent / "backups").glob("before-restore-*.zip"))


def test_invalid_json_and_forged_schema_are_rejected(client, tmp_path):
    assert (
        client.post(
            "/api/data/restore/preview",
            files={"file": ("bad.json", b"[]", "application/json")},
        ).status_code
        == 422
    )
    backup = tmp_path / "forged.sqlite3"
    backup.write_bytes(client.get("/api/data/backup").content)
    with sqlite3.connect(backup) as c:
        c.execute("ALTER TABLE tasks ADD COLUMN unexpected TEXT")
    c.close()  # Serialize the committed WAL changes before uploading the file bytes.
    response = client.post(
        "/api/data/restore/preview",
        files={
            "file": ("bad.sqlite3", backup.read_bytes(), "application/octet-stream")
        },
    )
    assert response.status_code == 422


def test_interrupted_restore_is_recovered_on_next_start(client, app, tmp_path, clock):
    client.post("/api/tasks", json={**task(), "title": "中断前数据"})
    backup = app.state.db.path.parent / "backups" / "interrupted.zip"
    backup.parent.mkdir(exist_ok=True)
    backup.write_bytes(client.get("/api/data/archive").content)
    marker = app.state.db.path.parent / "restore-in-progress.json"
    marker.write_text(json.dumps({"backup": str(backup.resolve())}))
    with app.state.db.transaction(write=True) as c:
        c.execute("DELETE FROM tasks")
    assert client.get("/api/tasks").status_code == 503
    with TestClient(
        create_app(app.state.db.path, clock=clock, access_token="")
    ) as restarted:
        assert restarted.get("/api/tasks").json()[0]["title"] == "中断前数据"
        assert restarted.get("/api/data/integrity").status_code == 200
    assert not marker.exists()


def test_mistake_trend_keeps_real_creation_and_deletion_events(client):
    m = client.post(
        "/api/mistakes", json={"title": "趋势题", "question": "题目"}
    ).json()
    before = client.get("/api/analytics?start=2026-10-17&end=2026-10-17").json()[
        "daily"
    ][0]
    assert before["new_mistakes"] == 1 and before["mistake_total"] == 1
    client.delete(f"/api/mistakes/{m['id']}")
    after = client.get("/api/analytics?start=2026-10-17&end=2026-10-17").json()[
        "daily"
    ][0]
    assert (
        after["new_mistakes"] == 1
        and after["removed_mistakes"] == 1
        and after["mistake_total"] == 0
    )
