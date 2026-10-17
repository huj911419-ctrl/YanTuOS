from pathlib import Path
import sqlite3
import tempfile
import uuid
import zipfile
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import Field
from ..schemas import Input
from ..services.backup import (
    MAX_ARCHIVE,
    make_archive,
    prepare_restore,
    activate_restore,
    validate_database,
    validate_files,
)


class RestoreInput(Input):
    stage_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    confirmation: str


def router(db, now):
    api = APIRouter(prefix="/api/data")
    stages = {}

    @api.get("/archive")
    def archive():
        folder = Path(tempfile.mkdtemp(prefix="yantu-archive-"))
        path = folder / "yantu-backup.zip"
        try:
            make_archive(db, path)
        except Exception:
            import shutil

            shutil.rmtree(folder)
            raise
        import shutil

        return FileResponse(
            path,
            filename=f"yantu-full-{now().strftime('%Y%m%d-%H%M%S')}.zip",
            background=BackgroundTask(shutil.rmtree, folder),
        )

    @api.get("/integrity")
    def integrity():
        with db.lock:
            try:
                version = validate_database(db.path)
                validate_files(db.path, db.path.parent / "uploads")
            except (ValueError, sqlite3.Error) as exc:
                raise HTTPException(422, str(exc)) from exc
        return {"integrity": "ok", "attachments": "ok", "schema_version": version}

    @api.post("/restore/preview")
    async def preview(file: UploadFile):
        # Stream upload to disk to keep memory bounded; no existing data is changed.
        folder = db.path.parent / "imports"
        folder.mkdir(exist_ok=True, mode=0o700)
        ident = uuid.uuid4().hex
        source = folder / (ident + ".upload")
        total = 0
        try:
            with source.open("xb") as out:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_ARCHIVE:
                        raise HTTPException(413, "导入文件超过 512 MB。")
                    out.write(chunk)
            source.chmod(0o600)
            from starlette.concurrency import run_in_threadpool

            summary = await run_in_threadpool(prepare_restore, source, folder / ident)
            stages[ident] = folder / ident
            return {
                **summary,
                "stage_id": ident,
                "warning": "确认恢复会替换当前学习数据库和附件。程序会先保存可回滚的完整备份。",
            }
        except (ValueError, sqlite3.Error, OSError, zipfile.BadZipFile) as exc:
            raise HTTPException(422, "无法导入：" + str(exc)) from exc
        finally:
            source.unlink(missing_ok=True)
            await file.close()

    @api.post("/restore/confirm")
    def restore(data: RestoreInput):
        if data.confirmation != "覆盖当前学习数据":
            raise HTTPException(422, "请输入“覆盖当前学习数据”明确确认。")
        stage = stages.pop(data.stage_id, None)
        if stage is None:
            raise HTTPException(404, "预览已失效，请重新导入。")
        try:
            return activate_restore(db, stage)
        except (ValueError, sqlite3.Error, OSError, zipfile.BadZipFile) as exc:
            raise HTTPException(422, "恢复失败，原始快照已保留：" + str(exc)) from exc

    return api
