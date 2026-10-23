from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.schemas import (
    DbState,
    ExtractionRequest,
    ExtractionStartResponse,
    ExtractionStatus,
    PasteRequest,
    UploadBatchResponse,
    UploadItemResult,
)
from app.services.extractor import extract_upload
from app.services.parsers import ALLOWED_EXTENSIONS, ParseError, parse_upload
from app.storage import (
    StorageError,
    claim_extractions,
    create_upload,
    ensure_storage,
    get_text,
    read_state,
    reset_interrupted_extractions,
    set_extraction,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage()
    reset_interrupted_extractions()
    yield


app = FastAPI(title="CourseBrief", lifespan=lifespan)


@app.middleware("http")
async def disable_static_cache(request: Request, call_next):
    """Serve front-end assets fresh; this local app has no build hashes."""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(StorageError)
async def storage_error_handler(_, exc: StorageError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/state", response_model=DbState)
def state() -> DbState:
    return read_state()


@app.get("/api/uploads/{upload_id}/text", response_class=PlainTextResponse)
def upload_text(upload_id: str) -> str:
    try:
        return get_text(upload_id)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/uploads", response_model=UploadBatchResponse)
async def upload_documents(
    files: Annotated[list[UploadFile], File()],
    course_hint: Annotated[str | None, Form()] = None,
) -> UploadBatchResponse:
    settings = get_settings()
    if len(files) > settings.max_files_per_upload:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files; maximum is {settings.max_files_per_upload}.",
        )

    items: list[UploadItemResult] = []
    max_bytes = settings.max_upload_mb * 1024 * 1024

    for file in files:
        filename = file.filename or "upload"
        ext = Path(filename).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            items.append(
                UploadItemResult(
                    filename=filename,
                    error=f"Unsupported file type: {ext or 'none'}",
                )
            )
            continue

        # 只读到上限加一字节即可判定超限，避免整个大文件进入内存。
        data = await file.read(max_bytes + 1)
        if len(data) > max_bytes:
            items.append(
                UploadItemResult(
                    filename=filename,
                    error=f"File is too large; maximum is {settings.max_upload_mb} MB.",
                )
            )
            continue

        try:
            text = parse_upload(filename, data)
            if len(text) > settings.max_doc_chars:
                raise ParseError(
                    f"Document is too long; maximum is {settings.max_doc_chars} characters."
                )
        except ParseError as exc:
            upload_id, _ = create_upload(
                "",
                "upload",
                original_filename=filename,
                course_hint=course_hint,
                original_bytes=data,
                original_ext=ext,
            )
            set_extraction(upload_id, ExtractionStatus.failed, error=str(exc))
            items.append(
                UploadItemResult(
                    filename=filename,
                    upload_id=upload_id,
                    error=str(exc),
                )
            )
            continue

        upload_id, _ = create_upload(
            text,
            "upload",
            original_filename=filename,
            course_hint=course_hint,
            original_bytes=data,
            original_ext=ext,
        )
        items.append(UploadItemResult(filename=filename, upload_id=upload_id))

    return UploadBatchResponse(items=items)


@app.post("/api/paste", response_model=UploadBatchResponse)
def paste_text(payload: PasteRequest) -> UploadBatchResponse:
    settings = get_settings()
    if len(payload.text) > settings.max_doc_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Text is too long; maximum is {settings.max_doc_chars} characters.",
        )

    title = (payload.title or "").strip() or "Pasted text"
    upload_id, _ = create_upload(
        payload.text,
        "paste",
        original_filename=title,
        course_hint=payload.course_hint,
    )
    return UploadBatchResponse(
        items=[UploadItemResult(filename=title, upload_id=upload_id)]
    )


@app.post("/api/extractions", response_model=ExtractionStartResponse)
def start_extractions(
    payload: ExtractionRequest,
    background_tasks: BackgroundTasks,
) -> ExtractionStartResponse:
    state = read_state()
    if payload.upload_ids is None:
        upload_ids = [
            upload_id
            for upload_id, record in state.uploads.items()
            if record.extraction.status
            in {ExtractionStatus.pending, ExtractionStatus.failed}
        ]
    else:
        missing = [upload_id for upload_id in payload.upload_ids if upload_id not in state.uploads]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Upload not found: {', '.join(missing)}",
            )
        upload_ids = list(dict.fromkeys(payload.upload_ids))

    for upload_id in claim_extractions(upload_ids):
        background_tasks.add_task(extract_upload, upload_id)

    return ExtractionStartResponse(upload_ids=upload_ids)
