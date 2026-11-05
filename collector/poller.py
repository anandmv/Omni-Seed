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
import logging
import os
import sqlite3
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


async def poll_wearable_api(source_id: str, endpoint: str, auth_header: str) -> None:
    """Generic wearable vendor poller. Fetches latest data and enqueues it
    wrapped in the standard envelope.

    Args:
        source_id:   Unique source identifier (matches the `sources` table PK).
        endpoint:    URL to poll.
        auth_header: Full value for the Authorization header, e.g. "Bearer TOKEN".
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(endpoint, headers={"Authorization": auth_header})
            resp.raise_for_status()
            payload = resp.json()

        envelope = {
            "job_id": str(uuid.uuid4()),
            "source_type": "wearable",
            "source_id": source_id,
            "received_at": time.time(),
            "raw_payload": payload,
        }
        await enqueue(envelope)
    except httpx.HTTPError as e:
        print(f"Poll error for {source_id} at {endpoint}: {e}")
    except Exception as e:
        print(f"Unexpected error polling {source_id}: {e}")


async def poll_iot_platform(source_id: str, endpoint: str, auth_param: str) -> None:
    """Example poller for an IoT platform that requires fetch rather than push.

    Args:
        source_id:  Unique source identifier (matches the `sources` table PK).
        endpoint:   URL to poll.
        auth_param: API key value passed as the ``api_key`` query parameter.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(endpoint, params={"api_key": auth_param})
            resp.raise_for_status()
            payload = resp.json()

        envelope = {
            "job_id": str(uuid.uuid4()),
            "source_type": "iot",
            "source_id": source_id,
            "received_at": time.time(),
            "raw_payload": payload,
        }
        await enqueue(envelope)
    except httpx.HTTPError as e:
        print(f"Poll error for {source_id} at {endpoint}: {e}")
    except Exception as e:
        print(f"Unexpected error polling {source_id}: {e}")


def build_scheduler() -> AsyncIOScheduler:
    """Build the APScheduler instance by loading enabled polling sources from
    the ``sources`` DB table rather than hardcoding them here.

    Approach:
      1. Opens the SQLite DB synchronously (this runs once at startup, so the
         overhead of a sync call is negligible and avoids async-in-sync
         complexity during scheduler bootstrapping).
      2. Queries ``SELECT * FROM sources WHERE enabled = 1``.
      3. Registers one interval job per row using the appropriate poller:
         - ``source_type = 'wearable'`` → :func:`poll_wearable_api`
           (``auth_header`` column is the full "Bearer TOKEN" string)
         - ``source_type = 'iot'``      → :func:`poll_iot_platform`
           (``auth_param`` column is the raw API-key value)
      4. Logs a warning and returns an empty (but valid) scheduler if no
         enabled sources are found.
    """
    scheduler = AsyncIOScheduler()

    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM sources WHERE enabled = 1").fetchall()
        con.close()
    except Exception as exc:
        logging.warning("Could not load sources from DB (%s): %s", DB_PATH, exc)
        rows = []

    if not rows:
        logging.warning(
            "No enabled sources found in the 'sources' table — poller will not schedule any jobs. "
            "Set enabled=1 on at least one row to activate polling."
        )
        return scheduler

    for row in rows:
        source_id = row["source_id"]
        source_type = row["source_type"]
        endpoint = row["endpoint"]
        poll_minutes = row["poll_minutes"]

        if source_type == "wearable":
            auth_header = row["auth_header"] or ""
            scheduler.add_job(
                poll_wearable_api,
                "interval",
                minutes=poll_minutes,
                args=[source_id, endpoint, auth_header],
            )
        elif source_type == "iot":
            auth_param = row["auth_param"] or ""
            scheduler.add_job(
                poll_iot_platform,
                "interval",
                minutes=poll_minutes,
                args=[source_id, endpoint, auth_param],
            )
        else:
            logging.warning("Unknown source_type %r for source %r — skipping.", source_type, source_id)

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
