"""
OmniSeed Collector — Polling collectors

Handles pull-based ingestion for sources with their own API that must be
queried on a schedule (wearable vendor APIs, some IoT platforms that expose
a data-fetch endpoint rather than pushing).

Each source gets its own small poller function. Adding a new vendor means
writing one new poller and registering it below — no changes to the core
pipeline required.

Run with: python poller.py
"""

import asyncio
import json
import time
import uuid

import httpx
import redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

r = redis.Redis()
STREAM = "omniseed:jobs"


def enqueue(envelope: dict) -> None:
    r.xadd(STREAM, {"data": json.dumps(envelope)})


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
        enqueue(envelope)


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
        enqueue(envelope)


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


if __name__ == "__main__":
    scheduler = build_scheduler()
    scheduler.start()
    print("Polling collectors started. Press Ctrl+C to exit.")
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
