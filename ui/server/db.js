// OmniSeed UI backend — SQLite connection
//
// Uses the built-in node:sqlite module (Node 22+, stable in Node 26+).
// No native compilation required. The API is synchronous, same as
// better-sqlite3, so the rest of the codebase is unchanged.
//
// The UI backend only ever reads from analysis_results — it never writes
// raw data, since none persists past the analyser worker's cleanup step.

import { DatabaseSync } from 'node:sqlite';

const DB_PATH = process.env.OMNISEED_DB_PATH || '../../omniseed.db';

const db = new DatabaseSync(DB_PATH);
db.exec('PRAGMA journal_mode = WAL');

export default db;
