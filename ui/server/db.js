// OmniSeed UI backend — SQLite connection
//
// Uses better-sqlite3 (synchronous, simple, no separate DB server to run).
// The UI backend only ever reads from analysis_results — it never writes
// raw data, since none persists past the analyser worker's cleanup step.

import Database from 'better-sqlite3';

const DB_PATH = process.env.OMNISEED_DB_PATH || '../../omniseed.db';

const db = new Database(DB_PATH, { readonly: false, fileMustExist: true });
db.pragma('journal_mode = WAL');

export default db;
