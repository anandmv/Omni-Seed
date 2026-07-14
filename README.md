# OmniSeed

In-house data seed analyser: ingests fragmented data (IoT, wearables,
uploads), analyses it with a locally hosted LLM (LM Studio + Phi), and
stores only generated metadata/summaries long-term — all in a single
local SQLite file, no extra services required.

![OmniSeed architecture](assets/omniseed_architecture.svg)

See `PLAN.md` for the full architecture writeup.

## Layout

```
omniseed/
├── PLAN.md                    Full architecture & build plan
├── pyproject.toml              Python deps for collector + analyser (uv-managed)
├── collector/
│   ├── main.py                 FastAPI push endpoints (/ingest/*), writes jobs to SQLite
│   └── poller.py                Polling collectors for pull-based sources, same DB writes
├── analyser/
│   ├── prompts.py                Per-source-type prompt builders
│   └── worker.py                  Polls jobs table, calls LM Studio, persists results
├── db/
│   └── schema.sql                  SQLite schema — `jobs` doubles as the work queue
└── ui/
    ├── server/
    │   ├── package.json
    │   ├── db.js                    SQLite connection (better-sqlite3)
    │   └── routes/export.js         Express CSV/JSON/PDF export route
    └── client/
        └── ExportPanel.jsx           React export controls
```

## Why no message broker

The `jobs` table serves double duty as both the lifecycle/audit log and
the work queue:

- Collector processes (`main.py`, `poller.py`) insert a row with
  `status='received'` and the full ingestion envelope in `envelope_json`.
- The analyser worker polls for the oldest `received` row and claims it
  with an atomic `UPDATE ... WHERE status='received'` — the affected-row
  count tells it whether it won the claim, so multiple workers can run
  safely without double-processing a job.
- If a worker crashes mid-job, `reclaim_stale_jobs()` resets anything
  stuck in `processing` past a timeout back to `received` so another
  worker retries it — the same crash-safety a broker would give you,
  without running one.

This trades a small amount of polling latency (checked every couple of
seconds) for one less service to install, run, and monitor. If you later
need pub/sub fan-out, priority queues, or very high throughput, that's the
point to introduce a real broker — the schema and worker logic here are
intentionally simple so that migration wouldn't require touching the
collector or LLM logic.

## Running locally (recommended)

Use the included shell script for a local runloop:

```bash
./run-locally.sh init
./run-locally.sh start
```

Commands:

- `./run-locally.sh init`
  - creates `omniseed.db` from `db/schema.sql` if needed
  - installs Python dependencies with `uv`
  - installs Node dependencies for `ui/server`
- `./run-locally.sh start`
  - starts the FastAPI collector API on `http://localhost:8000`
  - starts the collector poller
  - starts the analyser worker
  - starts `ui/server/server.js` if present
- `./run-locally.sh stop`
  - stops the managed background processes

Manual steps (if you prefer them):

## Running locally (rough order)

1. Create the SQLite database from the schema:
   ```
   sqlite3 omniseed.db < db/schema.sql
   ```
2. Start LM Studio in server mode with a Phi model loaded (listens on
   `localhost:1234` by default).
3. Install Python deps and run the collector API:
   ```
   uv run uvicorn collector.main:app --reload --port 8000
   ```
4. Start the polling collectors:
   ```
   uv run collector/poller.py
   ```
5. Start the analyser worker:
   ```
   uv run analyser/worker.py
   ```
6. Install and start the Node UI server:
   ```
   cd ui/server && npm install && node server.js
   ```
   (wire up your own `server.js`/Express app importing `routes/export.js`)
7. Start the React client, using `ExportPanel` in your results view.

By default, the collector, poller, worker, and UI server all look for
`omniseed.db` in the working directory — set `OMNISEED_DB_PATH` as an
environment variable if you want it elsewhere.

## Notes

- All components are designed to run entirely on the local network — no
  external API calls for LLM inference or data storage.
- Raw payloads and uploaded files are deleted immediately after a job's
  summary is successfully persisted (see `analyser/worker.py:persist_and_cleanup`).
- This is a working skeleton, not a production-hardened system — auth,
  retry/backoff tuning, and monitoring are called out as next steps in
  `PLAN.md`.
