"""
OmniSeed Collector — Polling collectors

Handles pull-based ingestion for sources with their own API that must be
queried on a schedule (wearable vendor APIs, some IoT platforms that expose
a data-fetch endpoint rather than pushing).

Each source gets its own small poller function. Adding a new vendor means
writing one new poller and registering it below — no changes to the core
pipeline required. Jobs are written straight into the SQLite `jobs` table
(same as collector/main.py), so there's no separate broker to run.

Run with: uv run collector/poller.py
"""

import asyncio
import json
import os
import time
import uuid

import aiosqlite
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

DB_PATH = os.environ.get("OMNISEED_DB_PATH", "omniseed.db")


async def enqueue(envelope: dict) -> None:
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


async def poll_wearable_api(source_id: str, endpoint: str, api_token: str) -> None:
    """Generic wearable vendor poller. Fetches latest data and enqueues it
    wrapped in the standard envelope."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(endpoint, headers={"Authorization": f"Bearer {api_token}"})
        resp.raise_for_status()

        envelope = {
            "job_id": str(uuid.uuid4()),
            "source_type": "wearable",
            "source_id": source_id,
            "received_at": time.time(),
            "raw_payload": resp.json(),
        }
        await enqueue(envelope)


async def poll_iot_platform(source_id: str, endpoint: str, api_key: str) -> None:
    """Example poller for an IoT platform that requires fetch rather than push."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(endpoint, params={"api_key": api_key})
        resp.raise_for_status()

        envelope = {
            "job_id": str(uuid.uuid4()),
            "source_type": "iot",
            "source_id": source_id,
            "received_at": time.time(),
            "raw_payload": resp.json(),
        }
        await enqueue(envelope)


def build_scheduler() -> AsyncIOScheduler:
    """Register all known pollers here. In production, load these from the
    `sources` table (see db/schema.sql) instead of hardcoding."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        poll_wearable_api,
        "interval",
        minutes=15,
        args=["fitbit-user-123", "https://api.fitbit.example/v1/activity", "TOKEN_HERE"],
    )
    scheduler.add_job(
        poll_iot_platform,
        "interval",
        minutes=5,
        args=["greenhouse-sensor-01", "https://iot-platform.example/api/latest", "KEY_HERE"],
    )

    return scheduler


async def main() -> None:
    scheduler = build_scheduler()
    scheduler.start()
    print("Polling collectors started. Press Ctrl+C to exit.")
    try:
        await asyncio.Event().wait()  # sleep forever, cleanly interruptible
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
