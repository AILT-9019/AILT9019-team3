from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from app.main import app

SAMPLE_TEXT = "Assignment 1 is due on 24 October 2026 at 23:59."


def test_paste_creates_upload():
    with TestClient(app) as client:
        response = client.post(
            "/api/paste",
            json={
                "title": "Announcement",
                "course_hint": "COMP3230",
                "text": SAMPLE_TEXT,
            },
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["error"] is None
        upload_id = item["upload_id"]
        assert upload_id

        state = client.get("/api/state").json()
        assert upload_id in state["uploads"]
        upload = state["uploads"][upload_id]
        assert upload["source_type"] == "paste"
        assert upload["original_filename"] == "Announcement"
        assert upload["course_hint"] == "COMP3230"
        assert upload["extraction"]["status"] == "pending"

        text_response = client.get(f"/api/uploads/{upload_id}/text")
        assert text_response.status_code == 200
        assert text_response.text == SAMPLE_TEXT


def test_upload_txt_creates_upload():
    with TestClient(app) as client:
        response = client.post(
            "/api/uploads",
            files={"files": ("syllabus.txt", SAMPLE_TEXT.encode(), "text/plain")},
            data={"course_hint": "COMP3230"},
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["error"] is None
        upload_id = item["upload_id"]

        state = client.get("/api/state").json()
        upload = state["uploads"][upload_id]
        assert upload["source_type"] == "upload"
        assert upload["original_filename"] == "syllabus.txt"
        assert upload["original_file"].endswith(".txt")

        text_response = client.get(f"/api/uploads/{upload_id}/text")
        assert text_response.text == SAMPLE_TEXT


def test_upload_unsupported_file_is_reported():
    with TestClient(app) as client:
        response = client.post(
            "/api/uploads",
            files={"files": ("malware.exe", b"hello", "application/octet-stream")},
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["upload_id"] is None
        assert "Unsupported file type" in item["error"]

        state = client.get("/api/state").json()
        assert state["uploads"] == {}


def test_get_missing_text_returns_404():
    with TestClient(app) as client:
        response = client.get("/api/uploads/does-not-exist/text")
        assert response.status_code == 404


def test_oversized_upload_is_read_only_up_to_limit(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    original_read = UploadFile.read
    read_sizes = []

    async def track_read(self, size=-1):
        read_sizes.append(size)
        return await original_read(self, size)

    monkeypatch.setattr(UploadFile, "read", track_read)
    with TestClient(app) as client:
        response = client.post(
            "/api/uploads", files={"files": ("large.txt", b"x" * (2 * 1024 * 1024), "text/plain")},
        )
        assert response.status_code == 200
        assert "too large" in response.json()["items"][0]["error"]
        assert client.get("/api/state").json()["uploads"] == {}
    assert read_sizes == [1024 * 1024 + 1]
