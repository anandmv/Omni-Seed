"""
OmniSeed Analyser — Queue consumer / LM Studio worker

Polls the SQLite `jobs` table for rows with status='received', claims one
via an atomic UPDATE (so multiple workers can safely run without double-
processing the same job), sends it to a locally running LM Studio instance
(Phi model) for analysis, then persists metadata/summary and deletes the
raw payload — all as one logical operation, so a failure at any step
leaves the job claimable again and the raw data intact for retry.

No message broker required — the `jobs` table doubles as the work queue.

Requires:
  - LM Studio running in server mode on localhost:1234
  - A SQLite file at DB_PATH (created from db/schema.sql)

Run with: uv run analyser/worker.py
"""

import asyncio
import json
import os
import shutil
import socket
import time
import uuid
from typing import Any

import aiosqlite
import httpx
from pydantic import BaseModel, ValidationError

from prompts import PROMPT_VERSION, build_prompt

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
DB_PATH = os.environ.get("OMNISEED_DB_PATH", "omniseed.db")

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
POLL_INTERVAL_SECONDS = 2
STALE_LOCK_SECONDS = 300  # reclaim jobs stuck 'processing' from a crashed worker


class AnalysisResult(BaseModel):
    tags: list[str]
    summary: str
    anomaly_flag: bool
    measurements: dict[str, Any] | None = None
    system_fingerprint: str | None = None


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def reclaim_stale_jobs(db: aiosqlite.Connection) -> None:
    """Safety net: if a worker crashed mid-job, its 'processing' row would
    otherwise sit locked forever. Reset anything locked past the timeout
    back to 'received' so another worker can pick it up."""
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - STALE_LOCK_SECONDS))
    await db.execute(
        "UPDATE jobs SET status = 'received', locked_by = NULL, locked_at = NULL "
        "WHERE status = 'processing' AND locked_at < ?",
        (cutoff,),
    )
    await db.commit()


async def claim_next_job(db: aiosqlite.Connection) -> tuple[str, dict] | None:
    """Atomically claim the oldest 'received' job. Returns None if nothing
    is available or another worker won the race."""
    cursor = await db.execute(
        "SELECT job_id, envelope_json FROM jobs WHERE status = 'received' ORDER BY received_at LIMIT 1"
    )
    row = await cursor.fetchone()
    if row is None:
        return None

    job_id, envelope_json = row
    claim = await db.execute(
        "UPDATE jobs SET status = 'processing', locked_by = ?, locked_at = ? "
        "WHERE job_id = ? AND status = 'received'",
        (WORKER_ID, now_iso(), job_id),
    )
    await db.commit()

    if claim.rowcount == 0:
        return None  # another worker claimed it first

    return job_id, json.loads(envelope_json)


async def call_lm_studio(prompt: str) -> tuple[str, str | None]:
    schema = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relevant tags or categories"
            },
            "summary": {
                "type": "string",
                "description": "Concise summary of the analysis"
            },
            "anomaly_flag": {
                "type": "boolean",
                "description": "Whether an anomaly was detected"
            },
            "measurements": {
                "type": "object",
                "description": "Extracted numeric or measurable values"
            },
            "system_fingerprint": {
                "type": "string",
                "description": "Stable fingerprint if one can be inferred"
            }
        },
        "required": ["tags", "summary", "anomaly_flag"]
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                LM_STUDIO_URL,
                json={
                    "model": "phi-3.5",
                    "messages": [
                        {"role": "system", "content": "You are a precise data analysis assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "AnalysisResult",
                            "schema": schema,
                            "strict": True
                        }
                    }
                },
            )
            resp.raise_for_status()
        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Cannot connect to LM Studio at {LM_STUDIO_URL}. Start LM Studio and retry."
            ) from e
        except httpx.HTTPStatusError as e:
            body = e.response.text
            raise RuntimeError(
                f"LM Studio rejected the request with status {e.response.status_code}: {body.strip()}"
            ) from e

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
            fingerprint = data.get("system_fingerprint")
            return content, fingerprint
        except (KeyError, TypeError, IndexError) as e:
            raise RuntimeError(
                f"Unexpected LM Studio response shape: {json.dumps(data)}"
            ) from e


def parse_analysis_response(raw: str, fallback_system_fingerprint: str | None = None) -> AnalysisResult:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("LM Studio response was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("LM Studio response was not a JSON object")

    measurements = payload.get("measurements")
    if measurements is not None and not isinstance(measurements, dict):
        raise ValueError("measurements must be an object when provided")

    system_fingerprint = payload.get("system_fingerprint") or fallback_system_fingerprint
    payload = {
        "tags": payload.get("tags", []),
        "summary": payload.get("summary", ""),
        "anomaly_flag": payload.get("anomaly_flag", False),
        "measurements": measurements,
        "system_fingerprint": system_fingerprint,
    }
    return AnalysisResult.model_validate(payload)


async def analyse(envelope: dict) -> AnalysisResult:
    prompt = build_prompt(envelope)
    raw, fingerprint = await call_lm_studio(prompt)

    try:
        return parse_analysis_response(raw, fingerprint)
    except (ValidationError, ValueError):
        # One corrective retry: tell the model exactly what went wrong.
        correction_prompt = (
            prompt
            + f"\n\nYour previous response was not valid JSON matching the schema: {raw}\n"
            + "Please respond again with ONLY valid JSON matching the schema."
        )
        raw_retry, retry_fingerprint = await call_lm_studio(correction_prompt)
        return parse_analysis_response(raw_retry, retry_fingerprint or fingerprint)


async def ensure_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(job_id),
            source_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            tags TEXT,
            anomaly_flag INTEGER NOT NULL DEFAULT 0 CHECK (anomaly_flag IN (0, 1)),
            prompt_version TEXT NOT NULL DEFAULT 'v2',
            measurements TEXT,
            system_fingerprint TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )
        """
    )
    await db.commit()

    columns = {row[1] for row in await db.execute_fetchall("PRAGMA table_info(analysis_results)")}
    if "measurements" not in columns:
        await db.execute("ALTER TABLE analysis_results ADD COLUMN measurements TEXT")
    if "system_fingerprint" not in columns:
        await db.execute("ALTER TABLE analysis_results ADD COLUMN system_fingerprint TEXT")
    await db.commit()


async def persist_and_cleanup(db: aiosqlite.Connection, job_id: str, envelope: dict, result: AnalysisResult) -> None:
    """Single logical operation: write result, mark job complete, delete raw
    data. If any step raises, nothing here is committed/deleted and the
    job stays in 'processing' — reclaim_stale_jobs will make it retryable
    again after the timeout."""
    await db.execute(
        """
        INSERT INTO analysis_results
            (id, job_id, source_id, source_type, summary, tags, anomaly_flag, prompt_version, measurements, system_fingerprint)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            job_id,
            envelope["source_id"],
            envelope["source_type"],
            result.summary,
            json.dumps(result.tags),
            1 if result.anomaly_flag else 0,
            PROMPT_VERSION,
            json.dumps(result.measurements or {}),
            result.system_fingerprint,
        ),
    )
    await db.execute(
        "UPDATE jobs SET status = 'summarized', completed_at = ? WHERE job_id = ?",
        (now_iso(), job_id),
    )
    await db.commit()

    # Delete raw data only after the DB write above has committed successfully.
    if envelope["source_type"] == "upload":
        scratch_path = envelope["raw_payload"].get("scratch_path")
        if scratch_path:
            job_dir = os.path.dirname(scratch_path)
            shutil.rmtree(job_dir, ignore_errors=True)

    await db.execute("UPDATE jobs SET status = 'raw_deleted' WHERE job_id = ?", (job_id,))
    await db.commit()


async def log_failure(db: aiosqlite.Connection, job_id: str, error: str) -> None:
    await db.execute(
        "UPDATE jobs SET status = 'failed', error_message = ? WHERE job_id = ?",
        (error, job_id),
    )
    await db.commit()


async def worker_loop(db: aiosqlite.Connection) -> None:
    print(f"Analyser worker '{WORKER_ID}' started. Polling for jobs...")

    while True:
        await reclaim_stale_jobs(db)
        claimed = await claim_next_job(db)

        if claimed is None:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        job_id, envelope = claimed
        try:
            result = await analyse(envelope)
            await persist_and_cleanup(db, job_id, envelope, result)
        except Exception as e:
            print(f"Job {job_id} failed: {e}")
            await log_failure(db, job_id, str(e))


async def main() -> None:
    # WAL mode lets this worker (writer) and the UI backend (reader)
    # operate concurrently without locking issues at this scale.
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await ensure_schema(db)
        await worker_loop(db)


if __name__ == "__main__":
    asyncio.run(main())
