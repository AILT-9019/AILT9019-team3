import time
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import DateConfidence, ExtractedTask, TaskType
from app.services import extractor, llm_client


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


def test_continuation_receives_header_and_existing_assignment(monkeypatch):
    chunks = ["COMP3234\nGame House assignment. Implement a game house.", "Submit GameServer.py."]
    monkeypatch.setattr(extractor, "_chunk_text", lambda text: chunks)
    calls = []
    parent = ExtractedTask(
        course_name="COMP3234", title="Game House", task_type=TaskType.assignment,
        date_confidence=DateConfidence.unknown, source_quote="Implement a game house.",
    )

    def respond(prompt, hint):
        calls.append(prompt)
        return [parent] if len(calls) == 1 else []

    monkeypatch.setattr(extractor, "_extract_chunk", respond)
    upload = SimpleNamespace(
        original_filename="handout.pdf", course_hint=None, uploaded_at=datetime.now(timezone.utc),
    )
    result = extractor._extract_live("\n".join(chunks), upload)
    assert len(result) == 1
    assert '"title": "Game House"' in calls[1]
    assert "COMP3234" in calls[1]
    assert "Submit GameServer.py." in calls[1]


def test_continuation_adds_deadline_without_losing_assignment():
    from datetime import date

    parent = ExtractedTask(
        course_name="COMP3234", title="Game House", task_type=TaskType.assignment,
        date_confidence=DateConfidence.unknown, source_quote="Implement a game house.",
    )
    tasks = [parent]
    dated = parent.model_copy(update={
        "date_confidence": DateConfidence.exact, "due_date": date(2026, 11, 4),
        "source_quote": "Due Nov 4, 2026.",
    })
    extractor._merge_continuation(tasks, dated)
    assert len(tasks) == 1
    assert tasks[0].due_date == date(2026, 11, 4)
    extractor._merge_continuation(tasks, dated.model_copy(update={"due_date": date(2026, 11, 8)}))
    assert len(tasks) == 2


def test_assignment_handout_fits_single_chunk():
    from pathlib import Path

    from app.services.parsers import parse_upload

    path = Path(__file__).resolve().parents[1] / "test_files/program_assignment_handout-2.pdf"
    assert len(extractor._chunk_text(parse_upload(path.name, path.read_bytes()))) == 1


@pytest.mark.parametrize("failure", ["timeout", "503", "format-timeout"])
def test_llm_retries_transport_and_transient_errors(monkeypatch, failure):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(llm_client.time, "sleep", lambda seconds: None)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            if failure == "format-timeout":
                return httpx.Response(400)
            if failure == "503":
                return httpx.Response(503)
            raise httpx.ConnectTimeout("handshake timed out", request=request)
        if failure == "format-timeout" and len(calls) == 2:
            raise httpx.ConnectTimeout("handshake timed out", request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"tasks": []}'}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(llm_client.httpx, "Client", lambda **kwargs: client)
    assert llm_client.chat_completion("system", "user") == '{"tasks": []}'
    assert len(calls) == (3 if failure == "format-timeout" else 2)


def test_llm_persistent_network_failure_is_actionable(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(llm_client.time, "sleep", lambda seconds: None)
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectTimeout("handshake timed out", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(llm_client.httpx, "Client", lambda **kwargs: client)
    with pytest.raises(llm_client.LLMError, match="after 3 attempts"):
        extractor._extract_chunk("prompt", None)
    assert len(calls) == 3


def test_repeated_start_requests_do_not_schedule_duplicate_jobs(monkeypatch):
    import app.main as main_module

    calls = []
    monkeypatch.setattr(main_module, "extract_upload", calls.append)
    with TestClient(app) as client:
        uid = _paste(client, "Assignment due 2026-10-24.")
        first = client.post("/api/extractions", json={"upload_ids": [uid, uid]})
        second = client.post("/api/extractions", json={"upload_ids": [uid]})
        assert first.json()["upload_ids"] == [uid]
        assert second.json()["upload_ids"] == [uid]
    assert calls == [uid]


def test_duplicate_refresh_retries_after_task_change(monkeypatch):
    from app.schemas import TaskRecord
    from app.storage import create_upload, read_state, replace_tasks

    uid, _ = create_upload("Assignment source.", "paste")
    record = TaskRecord(
        id=f"{uid}_01", upload_id=uid, course_name="COMP3230", title="Assignment",
        task_type=TaskType.assignment, date_confidence=DateConfidence.unknown,
        source_quote="Assignment source.",
    )
    replace_tasks(uid, [record])
    calls = []

    def build(tasks):
        calls.append(tasks)
        if len(calls) == 1:
            replace_tasks(uid, [record.model_copy(update={"description": "Updated."})])
        return {}, None

    monkeypatch.setattr(extractor, "build_duplicate_groups", build)
    extractor._refresh_duplicate_groups()
    assert len(calls) == 2
    assert calls[1][0].description == "Updated."
    assert read_state().tasks[0].description == "Updated."
