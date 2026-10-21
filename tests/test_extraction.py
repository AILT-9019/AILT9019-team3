import time

from fastapi.testclient import TestClient

from app.main import app


def _wait_for_extraction(client: TestClient, upload_id: str, timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get("/api/state").json()
        status = state["uploads"][upload_id]["extraction"]["status"]
        if status in {"succeeded", "failed"}:
            return state
        time.sleep(0.05)
    raise AssertionError(f"Extraction did not finish for {upload_id}")


def _paste(client: TestClient, text: str) -> str:
    response = client.post(
        "/api/paste",
        json={"title": "Notice", "course_hint": "COMP3230", "text": text},
    )
    assert response.status_code == 200
    return response.json()["items"][0]["upload_id"]


def test_mock_extraction_with_exact_date():
    with TestClient(app) as client:
        upload_id = _paste(client, "Assignment 1 is due on 2026-10-24.")
        response = client.post("/api/extractions", json={"upload_ids": [upload_id]})
        assert response.status_code == 200
        assert response.json()["upload_ids"] == [upload_id]

        state = _wait_for_extraction(client, upload_id)
        assert state["uploads"][upload_id]["extraction"]["status"] == "succeeded"
        assert len(state["tasks"]) == 1
        task = state["tasks"][0]
        assert task["upload_id"] == upload_id
        assert task["course_name"] == "COMP3230"
        assert task["due_date"] == "2026-10-24"
        assert task["date_confidence"] == "exact"
        assert task["source_quote"].startswith("Assignment 1 is due")


def test_mock_extraction_without_date_is_unknown():
    with TestClient(app) as client:
        upload_id = _paste(client, "Read chapter 3 before class.")
        client.post("/api/extractions", json={"upload_ids": [upload_id]})

        state = _wait_for_extraction(client, upload_id)
        task = state["tasks"][0]
        assert task["due_date"] is None
        assert task["date_confidence"] == "unknown"
        assert task["ambiguity_reason"]


def test_start_extraction_for_missing_upload_returns_404():
    with TestClient(app) as client:
        response = client.post("/api/extractions", json={"upload_ids": ["missing"]})
        assert response.status_code == 404
