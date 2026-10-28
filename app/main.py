import asyncio
import html
import json
import logging
import re
import threading
import uuid
from pathlib import Path

import markdown
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

load_dotenv()

from app.config import STATIC_DIR, TEMPLATES_DIR, UPLOAD_DIR
from app.services.jobs import Job, store
from app.services.pipeline import STAGES, run_job

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".webm",
    ".avi",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024

LANGUAGES = [
    ("english", "English (Whisper)"),
    ("hinglish", "Hinglish / Indic (Sarvam)"),
]
LANGUAGE_NAMES = dict(LANGUAGES)

logger = logging.getLogger(__name__)

app = FastAPI(title="Lens", description="Turn recordings into decisions, actions, and answers.")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def render_markdown(text: str | None) -> Markup:
    if not text:
        return Markup("")
    escaped = html.escape(str(text))
    rendered = markdown.markdown(
        escaped,
        extensions=["fenced_code", "sane_lists", "tables"],
    )
    return Markup(rendered)


templates.env.filters["markdown"] = render_markdown


def _slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-._")
    return (slug[:60] or "lens").lower()


def _base_context(request: Request, **extra: object) -> dict[str, object]:
    context: dict[str, object] = {
        "request": request,
        "languages": LANGUAGES,
        "language_names": LANGUAGE_NAMES,
    }
    context.update(extra)
    return context


def _index_response(
    request: Request,
    *,
    error: str | None = None,
    youtube_url: str = "",
    language: str = "english",
    status_code: int = 200,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        _base_context(
            request,
            error=error,
            youtube_url=youtube_url,
            selected_language=language,
        ),
        status_code=status_code,
    )


async def _save_upload(upload: UploadFile, destination: Path) -> int:
    size = 0
    try:
        with destination.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise ValueError("The file is larger than the 500 MB limit.")
                handle.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return size


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return _index_response(request)


@app.post("/process")
async def process(
    request: Request,
    youtube_url: str = Form(""),
    file: UploadFile | None = File(None),
    language: str = Form("english"),
) -> Response:
    youtube_url = youtube_url.strip()
    language = language if language in LANGUAGE_NAMES else "english"
    upload = file if file is not None and file.filename else None

    if youtube_url and upload:
        return _index_response(
            request,
            error="Choose either a YouTube link or a file, not both.",
            youtube_url=youtube_url,
            language=language,
            status_code=400,
        )

    if not youtube_url and not upload:
        return _index_response(
            request,
            error="Add a YouTube link or choose an audio/video file first.",
            language=language,
            status_code=400,
        )

    job_id = uuid.uuid4().hex[:12]

    if youtube_url:
        if not re.match(r"^https?://", youtube_url, re.IGNORECASE):
            return _index_response(
                request,
                error="The YouTube link must start with http:// or https://.",
                youtube_url=youtube_url,
                language=language,
                status_code=400,
            )
        source = youtube_url
        source_label = youtube_url
    else:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            return _index_response(
                request,
                error=(
                    "Unsupported file type. Use MP4, MKV, MOV, WebM, AVI, MP3, "
                    "WAV, M4A, AAC, FLAC, or OGG."
                ),
                language=language,
                status_code=400,
            )
        destination = UPLOAD_DIR / f"{job_id}{suffix}"
        try:
            size = await _save_upload(upload, destination)
        except ValueError as exc:
            return _index_response(
                request,
                error=str(exc),
                language=language,
                status_code=400,
            )
        if size == 0:
            destination.unlink(missing_ok=True)
            return _index_response(
                request,
                error="The selected file is empty.",
                language=language,
                status_code=400,
            )
        source = str(destination)
        source_label = upload.filename

    job = Job(
        id=job_id,
        source=source,
        source_label=source_label,
        language=language,
    )
    store.create(job)
    threading.Thread(
        target=run_job,
        args=(job.id, job.source, job.language),
        daemon=True,
        name=f"lens-job-{job.id}",
    ).start()
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str) -> HTMLResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(
        request,
        "job.html",
        _base_context(request, job=job, stages=STAGES),
    )


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> JSONResponse:
    snapshot = store.snapshot(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(snapshot)


@app.get("/jobs/{job_id}/events")
async def job_events(request: Request, job_id: str) -> StreamingResponse:
    if store.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        while True:
            if await request.is_disconnected():
                break
            snapshot = store.snapshot(job_id)
            if snapshot is None:
                yield 'event: error\ndata: {"message": "Job not found"}\n\n'
                break
            yield f"data: {json.dumps(snapshot)}\n\n"
            if snapshot["status"] in {"complete", "error"}:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/jobs/{job_id}/chat")
def job_chat(request: Request, job_id: str, message: str = Form("")) -> Response:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    is_htmx = request.headers.get("HX-Request") == "true"

    def chat_response() -> Response:
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "partials/chat.html",
                {"job": job},
            )
        return RedirectResponse(f"/jobs/{job_id}#chat", status_code=303)

    if job.status != "complete" or not job.result:
        return chat_response()

    message = message.strip()[:2000]
    if not message:
        return chat_response()

    store.add_message(job_id, "user", message)
    try:
        answer = job.result["rag_chain"].invoke(message)
    except Exception:
        logger.exception("Chat failed for job %s", job_id)
        answer = "I could not answer that question right now. Please try again."
    store.add_message(job_id, "assistant", str(answer))
    return chat_response()


def _minutes_document(job: Job) -> str:
    result = job.result or {}
    return "\n".join(
        [
            f"# {result.get('title', 'Untitled recording')}",
            "",
            f"_Language: {LANGUAGE_NAMES.get(job.language, job.language)}_",
            "",
            "## Summary",
            "",
            str(result.get("summary", "")).strip(),
            "",
            "## Action items",
            "",
            str(result.get("action_items", "")).strip(),
            "",
            "## Key decisions",
            "",
            str(result.get("key_decisions", "")).strip(),
            "",
            "## Open questions",
            "",
            str(result.get("questions", "")).strip(),
            "",
        ]
    )


def _chat_document(job: Job) -> str:
    result = job.result or {}
    lines = [f"# Chat - {result.get('title', 'Untitled recording')}", ""]
    if not job.messages:
        lines.append("_No questions were asked._")
    for message in job.messages:
        speaker = "You" if message["role"] == "user" else "Lens"
        lines.extend([f"**{speaker}:** {message['content']}", ""])
    return "\n".join(lines)


def _attachment(content: str, filename: str) -> Response:
    return Response(
        content=content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/jobs/{job_id}/download/{artifact}")
def download(job_id: str, artifact: str) -> Response:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete" or not job.result:
        raise HTTPException(status_code=409, detail="Job is not complete yet")

    result = job.result
    slug = _slug(str(result.get("title", "lens")))
    artifacts = {
        "minutes": (lambda: _minutes_document(job), f"{slug}-minutes.md"),
        "summary": (lambda: str(result.get("summary", "")), f"{slug}-summary.md"),
        "transcript": (lambda: str(result.get("transcript", "")), f"{slug}-transcript.txt"),
        "chat": (lambda: _chat_document(job), f"{slug}-chat.md"),
    }
    if artifact not in artifacts:
        raise HTTPException(status_code=404, detail="Unknown download")

    builder, filename = artifacts[artifact]
    return _attachment(builder(), filename)


@app.post("/session/reset")
def reset_session() -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("lens_job")
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8501)

