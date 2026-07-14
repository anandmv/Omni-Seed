"""
OmniSeed Collector — REST API listener

Handles push-based ingestion from sources that can call us directly:
mobile/wearable companion apps, IoT gateways, and user-initiated uploads.

Jobs are written straight into the SQLite `jobs` table with status
'received' — this table doubles as the work queue, so there's no separate
broker to run. The analyser worker polls for 'received' rows.

Run with: uv run uvicorn collector.main:app --reload --port 8000
"""

import json
import os
import time
import uuid

import aiosqlite
from fastapi import BackgroundTasks, FastAPI, UploadFile
from pydantic import BaseModel

app = FastAPI(title="OmniSeed Collector")

DB_PATH = os.environ.get("OMNISEED_DB_PATH", "omniseed.db")
SCRATCH_DIR = "/tmp/omniseed"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB safety cap


class SensorPayload(BaseModel):
    device_id: str
    payload: dict  # deliberately loose — shape varies by device/vendor


async def enqueue(envelope: dict) -> None:
    """Insert a job row with status='received'. The analyser worker polls
    for these; no message broker involved."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO jobs (job_id, source_id, source_type, status, envelope_json, received_at)
            VALUES (?, ?, ?, 'received', ?, ?)
            """,
            (
                envelope["job_id"],
                envelope["source_id"],
                envelope["source_type"],
                json.dumps(envelope),
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(envelope["received_at"])),
            ),
        )
        await db.commit()


@app.post("/ingest/sensor")
async def ingest_sensor(data: SensorPayload, bg: BackgroundTasks):
    """Push endpoint for IoT devices (temperature, humidity, etc.)."""
    envelope = {
        "job_id": str(uuid.uuid4()),
        "source_type": "iot",
        "source_id": data.device_id,
        "received_at": time.time(),
        "raw_payload": data.payload,
    }
    bg.add_task(enqueue, envelope)
    return {"status": "accepted", "job_id": envelope["job_id"]}


@app.post("/ingest/wearable-event")
async def ingest_wearable_event(data: SensorPayload, bg: BackgroundTasks):
    """Push endpoint for wearables/apps that send events directly rather
    than requiring us to poll their API."""
    envelope = {
        "job_id": str(uuid.uuid4()),
        "source_type": "wearable",
        "source_id": data.device_id,
        "received_at": time.time(),
        "raw_payload": data.payload,
    }
    bg.add_task(enqueue, envelope)
    return {"status": "accepted", "job_id": envelope["job_id"]}


@app.post("/ingest/upload")
async def ingest_upload(file: UploadFile, bg: BackgroundTasks):
    """Handles user-uploaded files. Saves to a scratch directory that gets
    wiped once analysis completes (see analyser/worker.py persist_and_cleanup)."""
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(SCRATCH_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    dest_path = os.path.join(job_dir, file.filename)

    size = 0
    with open(dest_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                os.remove(dest_path)
                return {"status": "rejected", "reason": "file too large"}
            f.write(chunk)

    envelope = {
        "job_id": job_id,
        "source_type": "upload",
        "source_id": file.filename,
        "received_at": time.time(),
        "raw_payload": {"scratch_path": dest_path},
    }
    bg.add_task(enqueue, envelope)
    return {"status": "accepted", "job_id": job_id}
