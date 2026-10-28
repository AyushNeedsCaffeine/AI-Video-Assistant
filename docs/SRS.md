# Software Requirements Specification

**Project:** Lens — Meeting Intelligence Platform  
**Document version:** 1.0  
**Product baseline:** v1.0.0  
**Date:** 2026-10-27  
**Status:** Approved for v1; v2 and future scope are planned

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for Lens, a web application that turns a video or meeting recording into a transcript, summary, action items, key decisions, open questions, and a searchable meeting chat.

It also defines the planned v2 interface, the deferred Google Meet bot, and the future evaluation strategy using LangSmith.

### 1.2 Scope

**v1.0.0 (current baseline)**

- Streamlit web UI and CLI entry point
- YouTube URL or local audio/video input
- Audio extraction, conversion to mono 16 kHz WAV, and chunking
- English transcription with OpenAI Whisper
- Hinglish transcription with Sarvam AI
- AI-generated title and map-reduce summary
- Extraction of action items, key decisions, and open questions
- Per-meeting Chroma vector index and RAG chat over the transcript
- Downloadable transcript and meeting minutes

**v2.0.0 (planned)**

- New Python-first web interface using FastAPI, Uvicorn, Jinja2, HTMX, Alpine.js, Tailwind CSS, and vanilla JavaScript
- Improved navigation, progress feedback, result presentation, and chat experience
- Branded logo and a soft-reset action
- Background job handling with progress events
- Same meeting-intelligence features as v1

**Future scope (v3+)**

- Google Meet bot that joins a live meeting and captures audio/transcript
- Live transcript, speaker diarization, and end-of-meeting processing
- LangSmith-based evaluation, tracing, and regression testing

**Out of scope for v1/v2**

- Live meeting capture
- Multi-user authentication and billing
- Mobile applications
- Enterprise administration and compliance workflows

### 1.3 Definitions

| Term | Meaning |
|---|---|
| SRS | Software Requirements Specification |
| RAG | Retrieval-Augmented Generation |
| STT | Speech-to-text |
| Bot | Automated participant that joins a meeting to capture audio/transcript |
| Soft reset | Clear the current session/job state without restarting the server process |
| LangSmith | LangChain's platform for tracing, evaluation, and observability of LLM applications |
| WER | Word Error Rate |
| SSE | Server-Sent Events |

### 1.4 References

- Project `readme.md`
- Current implementation: `app.py`, `main.py`, `core/`, `utlis/`
- Mistral AI API documentation
- Sarvam AI speech-to-text documentation
- OpenAI Whisper repository
- yt-dlp, Chroma, LangChain, Streamlit documentation
- Google Meet Media API and Google Meet REST API documentation
- Recall.ai meeting-bot API documentation

---

## 2. Overall Description

### 2.1 Product Perspective

Lens is a local-first, single-user meeting intelligence application. v1 is implemented with Streamlit and the existing Python pipeline. v2 replaces the presentation layer with a FastAPI/Jinja2 application while reusing the pipeline.

The architecture is intentionally provider-agnostic so that future meeting sources (uploads, YouTube, and meeting bots) use the same transcription, summarization, extraction, and retrieval services.

### 2.2 User Classes

| User class | Needs |
|---|---|
| Individual user | Process recordings, review results, chat with the transcript, export minutes |
| Power user / developer | Run the CLI, configure API keys and models, inspect logs |
| Meeting host (future) | Invite a bot, consent to capture, receive minutes |
| Administrator (future) | Manage retention, usage, integrations, and access |

### 2.3 Operating Environment

- Python 3.12
- ffmpeg available on `PATH`
- Windows, WSL/Linux, or Docker
- Modern browser with JavaScript enabled
- Internet access for Mistral AI, Sarvam AI, YouTube, and any future bot provider

### 2.4 Constraints

- Mistral model availability depends on the API key's subscription tier.
- YouTube extraction depends on yt-dlp and may require cookies for restricted videos.
- Google Meet Media API is a restricted Developer Preview and is not available to new signups.
- Live capture requires participant consent and may be subject to local recording laws.
- LLM, embedding, and bot usage incur external costs.
- Sarvam AI is required only for Hinglish transcription.

### 2.5 Assumptions

- v1 and v2 are single-user and local by default.
- Users supply their own API keys through `.env`.
- Inputs are authorized by the user.
- Meetings are primarily English or Hinglish.
- A GPU is optional; CPU execution is supported.

---

## 3. Functional Requirements

### 3.1 v1 Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | The system shall accept a YouTube URL and download the audio track. | Must |
| FR-02 | The system shall accept a local audio or video file. | Must |
| FR-03 | The system shall convert input audio to mono 16 kHz WAV and split long recordings into chunks. | Must |
| FR-04 | The system shall transcribe English audio with Whisper and reuse the loaded model across chunks. | Must |
| FR-05 | The system shall transcribe Hinglish audio with Sarvam AI. | Must |
| FR-06 | The system shall generate a short professional meeting title. | Must |
| FR-07 | The system shall generate a map-reduce summary for long transcripts. | Must |
| FR-08 | The system shall extract action items with task, owner, and deadline when available. | Must |
| FR-09 | The system shall extract key decisions. | Must |
| FR-10 | The system shall extract open questions and follow-up topics. | Must |
| FR-11 | The system shall build an isolated vector index per processed recording. | Must |
| FR-12 | The system shall answer questions using only the transcript context. | Must |
| FR-13 | The system shall provide a Streamlit UI and a CLI. | Must |
| FR-14 | The UI shall show progress and readable errors for each pipeline stage. | Must |
| FR-15 | The user shall be able to download the transcript and meeting minutes. | Must |
| FR-16 | The CLI shall support an interactive chat loop after processing. | Must |

### 3.2 v2 Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-17 | The system shall serve the UI through FastAPI and Uvicorn. | Must |
| FR-18 | The UI shall be rendered with Jinja2 templates and enhanced with HTMX, Alpine.js, and vanilla JavaScript. | Must |
| FR-19 | The system shall show live stage progress using SSE or WebSocket events. | Must |
| FR-20 | The system shall run processing in a background job and return a job identifier immediately. | Must |
| FR-21 | The system should persist job status and results locally. v2.0 uses an in-memory job store; durable storage is planned for v2.1. | Should |
| FR-22 | The UI shall display a branded logo on all pages. | Must |
| FR-23 | Clicking the logo shall show a confirmation dialog and perform a soft reset. | Must |
| FR-24 | A soft reset shall clear the current session/job reference and return to the landing page without terminating the server or affecting other sessions. | Must |
| FR-25 | The UI shall provide result tabs for summary, action items, decisions, questions, and transcript. | Must |
| FR-26 | The UI shall provide chat with streaming or progressive responses where practical. | Should |
| FR-27 | The UI shall remain usable on desktop and narrow browser widths. | Should |
| FR-28 | The existing Streamlit UI may remain available until feature parity is reached. | Could |

### 3.3 Logo Behavior

- The logo is displayed in the header.
- Clicking the logo opens a confirmation dialog.
- Confirming calls `POST /session/reset`.
- The reset clears the current session and active job reference, then redirects to `/`.
- A true process restart is not exposed to normal users.
- Any administrative hard restart must be token-protected and documented as disruptive.

---

## 4. External Interface Requirements

### 4.1 User Interface

- Landing page with source selector (YouTube URL or file upload), language selector, and start action
- Processing page with stage tracker and cancellation where supported
- Results page with tabs and copy/download actions
- Chat panel with message history and anchored answers
- Logo with soft-reset confirmation
- Clear error messages and retry affordances

### 4.2 HTTP API (v2)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Landing page |
| POST | `/process` | Start a job from a URL or uploaded file |
| GET | `/jobs/{job_id}` | Job status and results |
| GET | `/jobs/{job_id}/events` | SSE progress stream |
| GET | `/api/jobs/{job_id}` | JSON status for polling fallback |
| POST | `/jobs/{job_id}/chat` | Ask a question about a completed job (HTMX partial or redirect) |
| POST | `/session/reset` | Soft reset |
| GET | `/jobs/{job_id}/download/{artifact}` | Download minutes, summary, transcript, or chat |
| POST | `/jobs/{job_id}/cancel` | Request cancellation (planned for v2.1) |
| GET | `/health` | Health check |
| POST | `/webhooks/meet` | Future meeting-bot webhook (disabled by default) |

### 4.3 External Services

| Service | Purpose | Required |
|---|---|---|
| Mistral AI | Title, summary, extraction, RAG chat | Yes |
| Sarvam AI | Hinglish STT | Only for Hinglish |
| yt-dlp / YouTube | Audio download | Only for YouTube input |
| HuggingFace embeddings | Local sentence embeddings | Yes |
| Chroma | Vector storage | Yes |
| Recall.ai or equivalent | Future meeting bot | Future |
| LangSmith | Future tracing and evaluation | Future |

### 4.4 Data Interfaces

- Local filesystem: downloads, temporary audio chunks, vector database
- SQLite (v2): job and result persistence
- `.env` / environment variables: secrets and configuration
- Exports: Markdown and plain text in v1; PDF and DOCX in future scope

---

## 5. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Performance | Cached pages respond within 300 ms; long-running work is asynchronous |
| NFR-02 | Performance | Progress updates are emitted at least every few seconds per stage |
| NFR-03 | Reliability | A failed job retains an error state and does not corrupt previous results |
| NFR-04 | Reliability | Audio chunks and temporary files are cleaned up after processing |
| NFR-05 | Scalability | The job layer can move from an in-process worker to a queue-backed worker without changing the pipeline |
| NFR-06 | Security | API keys are read only from the environment and never written to logs or client responses |
| NFR-07 | Security | Uploaded filenames are sanitized and temporary files are isolated |
| NFR-08 | Privacy | Transcripts, audio, and vector indexes remain local by default |
| NFR-09 | Privacy | Future live capture must show a consent notice and comply with applicable law |
| NFR-10 | Usability | Every failure message identifies the failed stage and a next action |
| NFR-11 | Maintainability | UI, API, and pipeline logic are separated into distinct modules |
| NFR-12 | Portability | The application runs on Windows, WSL/Linux, and Docker |
| NFR-13 | Observability | Jobs have identifiers and structured logs; a health endpoint is available |
| NFR-14 | Accessibility | Keyboard navigation and readable contrast are supported |
| NFR-15 | Compatibility | The application targets Python 3.12 and the pinned dependency set |

---

## 6. Data Requirements

### 6.1 Entities

| Entity | Key fields |
|---|---|
| Meeting | id, title, source_type, source_reference, language, created_at |
| Job | id, meeting_id, status, stage, progress, error, started_at, completed_at |
| TranscriptSegment | job_id, start_time, end_time, speaker, text |
| Result | job_id, summary, action_items, key_decisions, open_questions |
| ChatMessage | job_id, role, content, created_at |
| Artifact | job_id, type, path, created_at |
| VectorCollection | collection_name, job_id, embedding_model |

### 6.2 Retention

- v1/v2: data remains local until the user deletes it.
- Future: configurable retention, deletion, and export policies.
- Secrets are never persisted in job records, logs, or exports.

---

## 7. Target Architecture

### 7.1 v1

```
Streamlit UI / CLI
        |
        v
core pipeline: audio -> transcription -> LLM -> Chroma/RAG
```

### 7.2 v2

```
Browser (HTML/CSS/JS, HTMX, Alpine.js)
        |
        v
FastAPI + Uvicorn + Jinja2
        |
        +-- API routes
        +-- Job service -- worker --> core pipeline
        |                              |
        |                              +--> Mistral, Sarvam, Whisper, Chroma
        |
        +-- In-memory job store (v2.0) / SQLite (v2.1)
        +-- Templates and static assets
```

### 7.3 Design Rules

- Reuse `core/` behind a service interface.
- One vector collection per recording.
- Never expose secrets to templates or browser code.
- Prefer server-rendered HTML with progressive enhancement over a large JavaScript framework.
- Keep a CLI entry point for automation and debugging.

---

## 8. Future Scope

### 8.1 Google Meet Bot

**Objective:** allow a user to submit a Google Meet link, have a bot join the meeting, capture the conversation, and generate the same transcript, summary, decisions, action items, questions, and minutes after the meeting.

**Candidate requirements**

1. Validate Google Meet URLs.
2. Create a bot with a visible name and consent disclosure.
3. Join the meeting and handle waiting rooms or admission prompts.
4. Capture mixed audio and, when available, per-participant audio.
5. Receive real-time transcript events.
6. Display a live transcript and live meeting status in the UI.
7. Detect meeting end and finalize the recording.
8. Diarize speakers and attribute utterances to participants.
9. Run the existing post-meeting pipeline.
10. Deliver minutes by email, download, or integration.
11. Keep an audit log of consent and bot activity.

**Integration options**

| Option | Assessment |
|---|---|
| Google Meet Media API | Real-time audio/video, but Developer Preview, no new signups, restricted scopes, Workspace/admin/host consent |
| Third-party bot API (e.g. Recall.ai) | Recommended for future implementation; reliable Meet support, real-time transcript/audio, webhooks |
| Self-hosted browser bot | Possible but brittle because of waiting rooms, host admission, anti-bot measures, and terms-of-service risk |
| Upload recording/transcript | Fallback that requires no live bot |

**Deferred decision:** implementation is intentionally postponed for several months. The v2 ingestion layer should keep a provider interface so this can be added without rewriting the pipeline.

### 8.2 LangSmith Evaluation and Observability

**Objective:** measure and improve the quality of transcription, summaries, extraction, and RAG answers, and catch regressions before releases.

**Planned requirements**

1. Trace every LLM, extraction, and RAG call for each job.
2. Group traces by job, meeting, prompt version, and model.
3. Build offline evaluation datasets from representative meeting transcripts.
4. Evaluate:
   - transcription WER where reference transcripts exist
   - summary coverage and faithfulness
   - action-item precision and recall
   - decision and open-question extraction quality
   - RAG groundedness and answer relevance
   - latency and token cost per stage
5. Add regression gates before changing prompts, models, or chunking settings.
6. Track prompt and model versions with results.
7. Sample production traces and redact PII before upload.
8. Make tracing opt-in through environment variables.

**Candidate metrics**

| Area | Metric |
|---|---|
| Transcription | WER, diarization error rate (future) |
| Summary | Faithfulness, coverage, conciseness |
| Extraction | Precision, recall, F1 |
| RAG | Context relevance, groundedness, answer relevance |
| Operations | Latency, token usage, error rate, cost per meeting |

**Privacy:** tracing must never send raw audio. Transcripts are sent only when explicitly enabled, with redaction and sampling.

### 8.3 Other Future Improvements

- Multi-user authentication and per-user data isolation
- PDF and DOCX export
- Calendar, Slack, Notion, and email integrations
- Live meeting summaries and alerts
- Local/offline LLM and STT options
- Additional languages and improved Hinglish handling
- Analytics dashboard and usage controls
- Docker images and CI/CD pipelines

---

## 9. Acceptance Criteria

### 9.1 v1.0.0

- A YouTube URL or local file can be processed successfully.
- The result contains title, summary, action items, key decisions, open questions, and transcript.
- RAG chat answers only from the transcript context.
- Transcript and minutes download successfully.
- Errors are surfaced without crashing the UI.

### 9.2 v2.0.0

- The application is served through FastAPI/Uvicorn with Jinja2 templates.
- Live progress is visible for each pipeline stage.
- Results and chat are available in the new interface.
- Clicking the logo provides a confirmation and performs a soft reset without terminating the server.
- The existing pipeline behavior is preserved.
- Chat works both with HTMX progressive enhancement and with a plain form-post fallback.
- Persistence, cancellation, automated tests, and a Docker deployment path are scheduled for v2.1.

---

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Mistral model unavailable on the key's tier | Pipeline failures | Configurable `MISTRAL_MODEL`; fail with clear message |
| YouTube blocks downloads | Ingestion failure | Keep yt-dlp updated; optional browser cookies |
| API rate limits | Partial results | Retries with backoff; clear errors |
| Large recordings exhaust memory | Crash | Chunking and background workers |
| Google Meet platform restrictions | Bot infeasible | Use a third-party bot provider; keep upload fallback |
| Recording consent and privacy law | Legal exposure | Explicit consent and retention controls |
| Evaluation data leaks PII | Privacy breach | Redaction, sampling, opt-in tracing |
| LLM output quality regressions | User trust | LangSmith evaluation gates |

---

## 11. Milestones

| Milestone | Deliverable |
|---|---|
| M1 | v1.0.0: runtime fixes, model configuration, yt-dlp update, SRS |
| M2 | v2.0.0: FastAPI/Jinja2/HTMX UI, job progress, logo soft reset, results, chat |
| M3 | v2.1: persistence, exports, tests, Docker |
| M4 | Future: Google Meet bot integration |
| M5 | Future: LangSmith tracing and evaluation gates |

---

## 12. Approval

| Role | Name | Date |
|---|---|---|
| Project owner | Ayush Jain | 2026-10-27 |
| Implementation | Lens engineering | 2026-10-27 |
