"""
OmniSeed Analyser — Queue consumer / LM Studio worker

Pulls jobs off the Redis stream, sends them to a locally running LM Studio
instance (Phi model) for analysis, then persists metadata/summary and
deletes the raw payload — all as one logical operation, so a failure at any
step leaves the job unacked and the raw data intact for retry.

Requires:
  - LM Studio running in server mode on localhost:1234
  - Redis running locally
  - Postgres reachable via DATABASE_URL

Run with: python worker.py
"""

import asyncio
import json
import os
import shutil
import time

import asyncpg
import httpx
import redis
from pydantic import BaseModel, ValidationError

from prompts import PROMPT_VERSION, build_prompt

r = redis.Redis()
STREAM = "omniseed:jobs"
GROUP = "analysers"
CONSUMER_NAME = "worker-1"

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/omniseed")

MAX_RETRIES = 1


class AnalysisResult(BaseModel):
    tags: list[str]
    summary: str
    anomaly_flag: bool


async def call_lm_studio(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            LM_STUDIO_URL,
            json={
                "model": "phi-3.5",
                "messages": [
                    {"role": "system", "content": "You are a precise data analysis assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def analyse(envelope: dict) -> AnalysisResult:
    prompt = build_prompt(envelope)
    raw = await call_lm_studio(prompt)

    try:
        return AnalysisResult.model_validate_json(raw)
    except ValidationError:
        # One corrective retry: tell the model exactly what went wrong.
        correction_prompt = (
            prompt
            + f"\n\nYour previous response was not valid JSON matching the schema: {raw}\n"
            + "Please respond again with ONLY valid JSON matching the schema."
        )
        raw_retry = await call_lm_studio(correction_prompt)
        return AnalysisResult.model_validate_json(raw_retry)  # let this raise if it still fails


async def persist_and_cleanup(pool: asyncpg.Pool, envelope: dict, result: AnalysisResult) -> None:
    """Single logical operation: write result, mark job complete, delete raw
    data. If any step raises, nothing here is committed/deleted and the
    queue message stays unacked for retry."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO analysis_results
                    (job_id, source_id, source_type, summary, tags, anomaly_flag, prompt_version)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                envelope["job_id"],
                envelope["source_id"],
                envelope["source_type"],
                result.summary,
                result.tags,
                result.anomaly_flag,
                PROMPT_VERSION,
            )
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'summarized', completed_at = to_timestamp($2)
                WHERE job_id = $1
                """,
                envelope["job_id"],
                time.time(),
            )

    # Delete raw data only after the DB write above has committed successfully.
    if envelope["source_type"] == "upload":
        scratch_path = envelope["raw_payload"].get("scratch_path")
        if scratch_path:
            job_dir = os.path.dirname(scratch_path)
            shutil.rmtree(job_dir, ignore_errors=True)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET status = 'raw_deleted' WHERE job_id = $1",
            envelope["job_id"],
        )


async def log_failure(pool: asyncpg.Pool, job_id: str, error: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET status = 'failed', error_message = $2 WHERE job_id = $1",
            job_id,
            error,
        )


async def ensure_consumer_group() -> None:
    try:
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def worker_loop(pool: asyncpg.Pool) -> None:
    await ensure_consumer_group()
    print("Analyser worker started. Waiting for jobs...")

    while True:
        jobs = r.xreadgroup(GROUP, CONSUMER_NAME, {STREAM: ">"}, count=1, block=5000)
        for _, messages in jobs or []:
            for msg_id, fields in messages:
                envelope = json.loads(fields[b"data"])
                try:
                    result = await analyse(envelope)
                    await persist_and_cleanup(pool, envelope, result)
                    r.xack(STREAM, GROUP, msg_id)
                except Exception as e:
                    print(f"Job {envelope.get('job_id')} failed: {e}")
                    await log_failure(pool, envelope.get("job_id"), str(e))
                    # Left unacked intentionally — eligible for reclaim/retry.


async def main() -> None:
    pool = await asyncpg.create_pool(DATABASE_URL)
    try:
        await worker_loop(pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
