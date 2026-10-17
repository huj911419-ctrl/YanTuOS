import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import uuid
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError
from ..schemas import Input, ShortText, Subject, LongText
from ..services.learning import row
from ..services.study import timestamp
from ..db import rows


class MaterialInput(Input):
    title: ShortText
    category: Subject = "未分类"
    notes: LongText = ""
    knowledge_id: int | None = None
    file_id: str | None = None


def router(db, now):
    api = APIRouter(prefix="/api")
    uploads = db.path.parent / "uploads"

    @api.post("/files", status_code=201)
    async def upload(file: UploadFile, kind: Literal["image", "material"] = "material"):
        content = await file.read(20 * 1024 * 1024 + 1)
        await file.close()
        if not content or len(content) > 20 * 1024 * 1024:
            raise HTTPException(413, "请选择非空且不超过 20 MB 的文件。")
        name = Path((file.filename or "文件").replace("\\", "/")).name[:200]
        suffix = Path(name).suffix.lower()
        mime = ""
        if kind == "image":
            try:
                with Image.open(io.BytesIO(content)) as im:
                    if (
                        im.format not in ("PNG", "JPEG", "WEBP")
                        or im.width * im.height > 25_000_000
                    ):
                        raise ValueError()
                    mime = {
                        "PNG": "image/png",
                        "JPEG": "image/jpeg",
                        "WEBP": "image/webp",
                    }[im.format]
                    im.verify()
            except (
                UnidentifiedImageError,
                ValueError,
                OSError,
                Image.DecompressionBombError,
            ) as exc:
                raise HTTPException(
                    422,
                    "图片需为有效的 PNG、JPEG 或 WebP，最多 2500 万像素。HEIC 请先导出为 JPEG。",
                ) from exc
        elif suffix in (".md", ".txt"):
            try:
                content.decode("utf-8")
            except UnicodeError as exc:
                raise HTTPException(422, "文本文件请使用 UTF-8 编码。") from exc
            mime = "text/plain"
        elif suffix == ".pdf" and content.startswith(b"%PDF-"):
            mime = "application/pdf"
        else:
            raise HTTPException(422, "资料支持 UTF-8 Markdown、TXT 和 PDF。")
        ident = uuid.uuid4().hex
        uploads.mkdir(exist_ok=True, parents=True, mode=0o700)
        path = uploads / ident
        with path.open("xb") as f:
            f.write(content)
        path.chmod(0o600)
        try:
            with db.transaction(write=True) as c:
                c.execute(
                    "INSERT INTO files VALUES (?,?,?,?,?,?,?)",
                    (
                        ident,
                        name,
                        mime,
                        kind,
                        len(content),
                        hashlib.sha256(content).hexdigest(),
                        timestamp(now()),
                    ),
                )
                return dict(row(c, "files", ident))
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @api.get("/files")
    def list_files():
        with db.transaction() as c:
            return rows(
                c.execute(
                    "SELECT f.*,(SELECT COUNT(*) FROM materials WHERE file_id=f.id)+(SELECT COUNT(*) FROM mistake_files WHERE file_id=f.id) reference_count FROM files f ORDER BY created_at DESC"
                )
            )

    @api.get("/files/{ident}")
    def get_file(ident: str, inline: bool = False):
        with db.transaction() as c:
            f = row(c, "files", ident)
        path = uploads / f["id"]
        if not path.is_file():
            raise HTTPException(404, "附件文件缺失，请检查完整备份。")
        return FileResponse(
            path,
            filename=f["name"],
            media_type=f["mime"],
            content_disposition_type="inline"
            if inline and f["kind"] == "image"
            else "attachment",
        )

    @api.delete("/files/{ident}", status_code=204)
    def delete_file(ident: str):
        with db.transaction(write=True) as c:
            f = row(c, "files", ident)
            if c.execute(
                "SELECT 1 FROM mistake_files WHERE file_id=? UNION ALL SELECT 1 FROM materials WHERE file_id=?",
                (ident, ident),
            ).fetchone():
                raise HTTPException(409, "附件仍被使用，请先解除关联。")
            c.execute("DELETE FROM files WHERE id=?", (ident,))
            (uploads / f["id"]).unlink(missing_ok=True)

    def extract(c, data):
        if data.knowledge_id:
            row(c, "knowledge_points", data.knowledge_id)
        if not data.file_id:
            return "", "none"
        file = row(c, "files", data.file_id)
        if file["kind"] != "material":
            raise HTTPException(422, "请选择学习资料文件。")
        path = uploads / file["id"]
        if file["mime"] == "text/plain":
            return path.read_text(encoding="utf-8")[:500000], "text"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[1] / "services/pdf_extract.py"
                    ),
                    str(path),
                ],
                capture_output=True,
                timeout=18,
                text=True,
            )
            output = json.loads(result.stdout)
            return output["text"], output["status"]
        except (subprocess.TimeoutExpired, ValueError, KeyError):
            return "", "unavailable"

    @api.get("/materials")
    def materials(
        q: str = Query("", max_length=200),
        category: str = "",
        knowledge_id: int | None = None,
    ):
        with db.transaction() as c:
            return rows(
                c.execute(
                    'SELECT m.*,f.name filename FROM materials m LEFT JOIN files f ON f.id=m.file_id WHERE (instr(m.title,?)>0 OR instr(m.notes,?)>0) AND (?="" OR m.category=?) AND (? IS NULL OR m.knowledge_id=?) ORDER BY m.updated_at DESC',
                    (q, q, category, category, knowledge_id, knowledge_id),
                )
            )

    @api.post("/materials", status_code=201)
    def create_material(data: MaterialInput):
        with db.transaction(write=True) as c:
            text, status = extract(c, data)
            stamp = timestamp(now())
            ident = c.execute(
                "INSERT INTO materials(title,category,notes,knowledge_id,file_id,extracted_text,extraction_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    data.title,
                    data.category,
                    data.notes,
                    data.knowledge_id,
                    data.file_id,
                    text,
                    status,
                    stamp,
                    stamp,
                ),
            ).lastrowid
            return dict(row(c, "materials", ident))

    @api.put("/materials/{ident}")
    def update_material(ident: int, data: MaterialInput):
        with db.transaction(write=True) as c:
            old = row(c, "materials", ident)
            if data.knowledge_id:
                row(c, "knowledge_points", data.knowledge_id)
            text, status = (
                extract(c, data)
                if old["file_id"] != data.file_id
                else (old["extracted_text"], old["extraction_status"])
            )
            c.execute(
                "UPDATE materials SET title=?,category=?,notes=?,knowledge_id=?,file_id=?,extracted_text=?,extraction_status=?,updated_at=? WHERE id=?",
                (
                    data.title,
                    data.category,
                    data.notes,
                    data.knowledge_id,
                    data.file_id,
                    text,
                    status,
                    timestamp(now()),
                    ident,
                ),
            )
            return dict(row(c, "materials", ident))

    @api.delete("/materials/{ident}", status_code=204)
    def delete_material(ident: int):
        with db.transaction(write=True) as c:
            row(c, "materials", ident)
            c.execute("DELETE FROM materials WHERE id=?", (ident,))

    @api.get("/materials/{ident}/export")
    def export_material(ident: int):
        with db.transaction() as c:
            m = row(c, "materials", ident)
            text = f"# {m['title']}\n\n分类：{m['category']}\n\n{m['notes']}\n\n## 提取文本\n\n{m['extracted_text']}"
        return Response(
            text,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="material-{ident}.md"'
            },
        )

    @api.get("/mistakes-export")
    def export_mistakes(
        knowledge_id: int | None = None, q: str = Query("", max_length=200)
    ):
        with db.transaction() as c:
            data = rows(
                c.execute(
                    "SELECT m.* FROM mistakes m WHERE (? IS NULL OR EXISTS(SELECT 1 FROM mistake_knowledge WHERE mistake_id=m.id AND knowledge_id=?)) AND (instr(title,?)>0 OR instr(question,?)>0) ORDER BY m.id",
                    (knowledge_id, knowledge_id, q, q),
                )
            )
            text = "# 研途 OS 错题导出\n\n"
            for m in data:
                names = [
                    r[0]
                    for r in c.execute(
                        "SELECT k.title FROM knowledge_points k JOIN mistake_knowledge mk ON mk.knowledge_id=k.id WHERE mistake_id=?",
                        (m["id"],),
                    )
                ]
                text += (
                    f"## {m['title']}\n\n科目：{m['subject']}；分类：{m['category']}；知识点："
                    + "、".join(names)
                    + "\n\n"
                )
                for label, key in [
                    ("题目", "question"),
                    ("错误答案", "wrong_answer"),
                    ("正确答案", "answer"),
                    ("错误原因", "error_reason"),
                    ("来源", "source"),
                ]:
                    text += f"### {label}\n\n{m[key]}\n\n"
        return Response(
            text,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="yantu-mistakes.md"'},
        )

    return api
