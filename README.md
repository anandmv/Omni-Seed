# OmniSeed

In-house data seed analyser: ingests fragmented data (IoT, wearables,
uploads), analyses it with a locally hosted LLM (LM Studio + Phi), and
stores only generated metadata/summaries long-term.

See `PLAN.md` for the full architecture writeup.

## Layout

```
omniseed/
├── PLAN.md                    Full architecture & build plan
├── requirements.txt            Python deps for collector + analyser
├── collector/
│   ├── main.py                 FastAPI push endpoints (/ingest/*)
│   └── poller.py                Polling collectors for pull-based sources
├── analyser/
│   ├── prompts.py                Per-source-type prompt builders
│   └── worker.py                  Queue consumer, calls LM Studio, persists results
├── db/
│   └── schema.sql                  Postgres schema (jobs, analysis_results, sources)
└── ui/
    ├── server/
    │   ├── package.json
    │   └── routes/export.js         Express CSV/JSON/PDF export route
    └── client/
        └── ExportPanel.jsx           React export controls
```

## Running locally (rough order)

1. Start Postgres and Redis locally.
2. Apply the schema: `psql omniseed < db/schema.sql`
3. Start LM Studio in server mode with a Phi model loaded (listens on
   `localhost:1234` by default).
4. Install Python deps: `pip install -r requirements.txt`
5. Start the collector API: `uvicorn collector.main:app --reload --port 8000`
6. Start the polling collectors: `python collector/poller.py`
7. Start the analyser worker: `python analyser/worker.py`
8. Install and start the Node UI server (`ui/server`), then the React
   client, wiring `ExportPanel` into your results view.

## Notes

- All components are designed to run entirely on the local network — no
  external API calls for LLM inference or data storage.
- Raw payloads and uploaded files are deleted immediately after a job's
  summary is successfully persisted (see `analyser/worker.py:persist_and_cleanup`).
- This is a working skeleton, not a production-hardened system — auth,
  retry/backoff tuning, and monitoring are called out as next steps in
  `PLAN.md`.
