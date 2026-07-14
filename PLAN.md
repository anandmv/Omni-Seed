# OmniSeed — Data Seed Analyser: Architecture & Build Plan

## Overview

OmniSeed is an in-house system for synthesizing, analyzing, and summarizing fragmented data from multiple sources (IoT sensors, wearables, user uploads), using a locally hosted LLM for analysis, with strict data retention rules: only generated metadata/summaries persist long-term.

**Chosen stack:**
- Collector: Python (FastAPI + polling workers)
- LLM: LM Studio, running Phi locally
- UI: Node.js (API layer) + React (frontend)
- Database: local Postgres or SQLite

---

## 1. Collector (Python)

A service with pluggable "connector" modules per source type, feeding a common ingestion queue.

- **REST API listener** — FastAPI exposing endpoints like `POST /ingest/{source_type}` for devices/apps that push data directly.
- **Polling collectors** — APScheduler or asyncio loop pulling from wearable vendor APIs (Fitbit, Garmin, etc.) on a schedule.
- **Normalization layer** — every payload is wrapped in a common envelope before moving downstream, so the analyser stays source-agnostic:

  ```json
  {
    "source_id": "...",
    "source_type": "iot | wearable | upload",
    "received_at": "...",
    "raw_payload": { }
  }
  ```

- **Queue** — Redis Streams or a SQLite-backed queue between collector and analyser, decoupling ingestion bursts from LLM processing time. Kept local to honor the in-house requirement.

---

## 2. LLM Analyser (LM Studio + Phi)

- Run LM Studio in **server mode**, exposing an OpenAI-compatible `/v1/chat/completions` endpoint on `localhost:1234`. No internet egress required.
- **Worker process** (Python): pulls envelopes off the queue, builds a prompt per source type, calls LM Studio, parses structured JSON output (tags, summary, anomaly flags, etc.).
- **Prompt strategy** — request strict JSON matching a schema; validate with Pydantic; retry with a corrective prompt on schema-validation failure.
- **Temp file handling** — uploaded files land in a scratch directory (`/tmp/omniseed/{job_id}/`) with a TTL. A cleanup step deletes the directory immediately after the summary is persisted, plus a timer-based sweep as a safety net for crashed jobs.

---

## 3. Data Privacy & Retention

- **Fully local:** DB + LLM inference both run in-house — no third-party API calls.
- **Retention enforcement** (built into the workflow, not a bolt-on cron job):
  1. Raw payload lives only in the queue + temp scratch space.
  2. On successful analysis, only `{metadata, summary, source_type, timestamp}` is written to the permanent DB.
  3. The queue message and temp file are deleted in the same step that confirms the DB write succeeded — avoids data loss on crash, and avoids lingering raw data on success.
- **Audit trail:** log job lifecycle events (received → processing → summarized → raw-deleted) without logging payload content — proves deletion happened without re-storing sensitive data.

---

## 4. UI (Node.js + React)

- **Backend:** Node.js/Express (or Fastify) API layer — talks only to the database, never touches raw data (since none persists).
- **Frontend:** React app with views for browsing summaries/metadata, filtering by source/date, and exporting results.
- **Export formats:** CSV/JSON via native handling, PDF via `pdfkit`, spreadsheet via `exceljs`.
- Keep this API on the same local network boundary as the DB — no need to expose it publicly for a fully in-house tool.

---

## Suggested Build Order

1. **Collector skeleton** — FastAPI + one polling connector, writing to a local queue. Get data flowing end-to-end with dummy processing first.
2. **LM Studio integration** — prompt/schema design, validate summarization quality before building UI around it.
3. **Retention/cleanup logic** — bake in early since it's a core requirement, not an afterthought.
4. **Node/React UI** — build against the DB schema once it's stable.
5. **Hardening pass** — error handling for malformed uploads, retry logic for LLM calls, monitoring for queue backlog.

---

## Open Design Questions (for later decisions)

- Exact DB schema for jobs / metadata / summaries tables
- Which wearable/IoT vendor APIs need first-class connectors
- Export format priorities (CSV vs PDF vs JSON) for the initial release
- Whether the temp-file cleanup timer runs as a background thread in the worker or a separate system cron job
