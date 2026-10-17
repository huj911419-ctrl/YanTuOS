from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest
from app.main import create_app


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 17, 2, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def app(tmp_path, clock):
    return create_app(tmp_path / "test.sqlite3", clock=clock, access_token="")


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
