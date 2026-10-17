"""Browser tests use a temporary database, never the user's study records."""

import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.main import create_app
from app.services.study import local_date, timestamp

if __name__ == "__main__":
    os.environ["YANTU_ALLOWED_ORIGINS"] = "http://127.0.0.1:18000"
    with tempfile.TemporaryDirectory(prefix="yantu-browser-test-") as folder:
        app = create_app(Path(folder) / "browser.sqlite3", access_token="")
        instant = datetime.now(timezone.utc)
        db = app.state.db
        db.initialize(timestamp(instant))
        # Clearly named due fixtures exist ONLY inside this temporary test DB.
        with db.transaction(write=True) as conn:
            for project in ("desktop-chromium", "mobile-webkit"):
                for outcome in ("remembered", "forgotten"):
                    title = f"E2E到期样本-{project}-{outcome}"
                    cur = conn.execute(
                        "INSERT INTO mistakes(title,subject,question,answer,error_reason,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                        (
                            title,
                            "数学",
                            "E2E 测试样本：1+1 等于多少？",
                            "2",
                            "E2E 临时数据",
                            timestamp(instant),
                            timestamp(instant),
                        ),
                    )
                    conn.execute(
                        "INSERT INTO review_schedules(mistake_id,due_date) VALUES (?,?)",
                        (cur.lastrowid, local_date(instant).isoformat()),
                    )
        uvicorn.run(app, host="127.0.0.1", port=18000, log_level="warning")
