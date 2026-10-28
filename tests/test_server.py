"""The server itself starts and serves the demo (catches import-time errors that unit tests miss)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_page_and_state():
    assert client.get("/").status_code == 200
    s = client.post("/api/reset").json()
    assert s["step"] == 0 and s["merchant"]["id"] == "M01"
    assert client.get("/api/state", params={"focus": "M02"}).json()["focus"] == "M02"


def test_story_through_the_api():
    s = client.post("/api/step", json={"n": 8}).json()
    assert s["merchant"]["case"]["state"] == "recovered"
    week = {r["date"]: r for r in client.get("/api/week/M01").json()["rows"]}
    assert week["2026-10-26"]["with"]["deducted"] == 1032
    assert client.post("/api/advance", json={"hours": 2}).status_code == 200
    assert client.get("/api/audit", params={"merchant": "M01"}).json()["total"] > 0
