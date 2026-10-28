import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from core.Summarize import generate_title, summarize
from core.extractor import (
    extract_action_items,
    extract_key_decisions,
    extract_questions,
)
from core.rag_engine import build_rag_chain
from core.transcriber import transcribe_chunk
from utlis.audio_processor import process_input

from app.config import UPLOAD_DIR
from app.services.jobs import store

logger = logging.getLogger(__name__)

STAGES = [
    ("audio", "Preparing audio"),
    ("transcribe", "Transcribing"),
    ("title", "Generating title"),
    ("summary", "Summarizing"),
    ("extract", "Extracting insights"),
    ("index", "Building chat index"),
]

STAGE_LABELS = dict(STAGES)


def _clean_title(title: str | None) -> str:
    cleaned = (title or "").strip()
    while cleaned and cleaned[0] in "\"'*":
        cleaned = cleaned[1:]
    while cleaned and cleaned[-1] in "\"'*":
        cleaned = cleaned[:-1]
    return cleaned.strip() or "Untitled recording"


def _friendly_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    lowered = text.lower()
    if "decoding failed" in lowered or "invalid data found" in lowered:
        return "Lens could not read this file. It may be corrupt or not a supported audio/video format."
    if "ffmpeg" in lowered and ("not found" in lowered or "winerror 2" in lowered):
        return "ffmpeg is not installed or not on PATH. Install ffmpeg and restart the server."
    if "sarvam_api_key" in lowered:
        return "Sarvam transcription is not configured. Add SARVAM_API_KEY to .env or choose English (Whisper)."
    if "429" in lowered or "rate limit" in lowered:
        return "An external AI service is rate-limited. Wait a moment and try again."
    if "401" in lowered or "403" in lowered or "unauthorized" in lowered:
        return "An external service rejected the request. Check your API keys and account quota."
    if (
        "youtube" in lowered
        or "yt-dlp" in lowered
        or "downloaderror" in exc.__class__.__name__.lower()
        or "unable to download" in lowered
    ):
        return "Lens could not download that video. Check that the link is public and still available."
    if not text:
        return "An unknown error occurred while processing the recording."
    if len(text) > 300:
        text = text[:297].rstrip() + "..."
    return text


def _cleanup_upload(source: str) -> None:
    try:
        path = Path(source).resolve()
        if not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
            return
        converted = path.with_suffix("")
        converted = converted.parent / f"{converted.name}_converted.wav"
        targets = [path, converted]
        targets.extend(converted.parent.glob(f"{converted.name}_chunk_*.wav"))
        for target in targets:
            if target.is_file():
                target.unlink()
    except OSError:
        logger.warning("Could not clean up upload %s", source, exc_info=True)


def run_job(job_id: str, source: str, language: str) -> None:
    try:
        store.update(
            job_id,
            status="running",
            stage="audio",
            progress=3,
            message=STAGE_LABELS["audio"],
        )
        chunks = process_input(source)
        total = max(len(chunks), 1)

        store.update(
            job_id,
            stage="transcribe",
            progress=10,
            message=f"Transcribing {total} chunk(s)",
        )
        parts: list[str] = []
        for index, chunk in enumerate(chunks, 1):
            store.update(
                job_id,
                progress=10 + int(35 * index / total),
                message=f"Transcribing chunk {index} of {total}",
            )
            text = transcribe_chunk(chunk, language=language)
            if text:
                parts.append(text)
        transcript = " ".join(parts).strip()
        if not transcript:
            raise RuntimeError("Transcription returned no text for this recording.")

        store.update(
            job_id,
            stage="title",
            progress=50,
            message=STAGE_LABELS["title"],
        )
        title = _clean_title(generate_title(transcript))

        store.update(
            job_id,
            stage="summary",
            progress=62,
            message=STAGE_LABELS["summary"],
        )
        summary = summarize(transcript)

        store.update(
            job_id,
            stage="extract",
            progress=76,
            message="Extracting action items",
        )
        action_items = extract_action_items(transcript)

        store.update(job_id, progress=82, message="Extracting key decisions")
        key_decisions = extract_key_decisions(transcript)

        store.update(job_id, progress=88, message="Extracting open questions")
        questions = extract_questions(transcript)

        store.update(
            job_id,
            stage="index",
            progress=94,
            message=STAGE_LABELS["index"],
        )
        rag_chain = build_rag_chain(transcript, collection_name=f"lens_{job_id}")

        store.update(
            job_id,
            status="complete",
            stage="done",
            progress=100,
            message="Ready",
            finished_at=datetime.now(timezone.utc).isoformat(),
            result={
                "title": title,
                "summary": summary,
                "action_items": action_items,
                "key_decisions": key_decisions,
                "questions": questions,
                "transcript": transcript,
                "rag_chain": rag_chain,
            },
        )
        _cleanup_upload(source)
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        store.update(
            job_id,
            status="error",
            stage="error",
            message="Processing failed",
            error=_friendly_error(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        _cleanup_upload(source)
