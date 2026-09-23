"""SQLite database helpers and a small, backwards-compatible schema migration."""
import sqlite3, json
from datetime import datetime, timezone
from .config import DB_PATH
from .security import encrypt, decrypt

def now():
    return datetime.now(timezone.utc).isoformat()

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def _columns(c, table):
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}

def init_db():
    c = conn()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,display_name TEXT,role TEXT DEFAULT 'researcher',created_at TEXT);
    CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT,research_question TEXT,framework TEXT,method TEXT,languages TEXT,created_at TEXT,updated_at TEXT,owner_id TEXT);
    CREATE TABLE IF NOT EXISTS project_members(project_id TEXT,user_id TEXT,role TEXT DEFAULT 'researcher',created_at TEXT,PRIMARY KEY(project_id,user_id));
    CREATE TABLE IF NOT EXISTS codes(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,definition TEXT,inclusion TEXT,exclusion TEXT,example TEXT,parent_id TEXT,theory TEXT,color TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,project_id TEXT,name TEXT,path TEXT,source_type TEXT,language TEXT,transcript TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS codings(id TEXT PRIMARY KEY,project_id TEXT,source_id TEXT,segment_id TEXT,quote TEXT,code_id TEXT,code_name TEXT,confidence REAL,rationale TEXT,status TEXT DEFAULT 'ai_suggested',model TEXT,created_at TEXT,reviewed_at TEXT,reviewer_id TEXT,run_id TEXT,start REAL,end REAL,speaker TEXT);
    CREATE TABLE IF NOT EXISTS anomalies(id TEXT PRIMARY KEY,project_id TEXT,label TEXT,description TEXT,metric TEXT,value TEXT,context TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT,event TEXT,details TEXT,created_at TEXT,user_id TEXT);
    CREATE TABLE IF NOT EXISTS coding_runs(id TEXT PRIMARY KEY,project_id TEXT,source_id TEXT,model TEXT,created_at TEXT,kind TEXT);
    CREATE TABLE IF NOT EXISTS memos(id TEXT PRIMARY KEY,project_id TEXT,source_id TEXT,title TEXT,body TEXT,created_at TEXT,updated_at TEXT);
    ''')
    # The original starter did not have these columns.  Adding them here lets
    # an existing user's database upgrade itself without losing research data.
    for table, col, ddl in [
        ("projects", "owner_id", "TEXT"),
        ("codes", "color", "TEXT"),
        ("codings", "reviewer_id", "TEXT"),
        ("codings", "run_id", "TEXT"),
        ("codings", "start", "REAL"),
        ("codings", "end", "REAL"),
        ("codings", "speaker", "TEXT"),
        ("audit", "user_id", "TEXT"),
    ]:
        if col not in _columns(c, table):
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    c.commit(); c.close()

def _decode_row(row):
    d = dict(row)
    for key in ("description", "research_question", "framework", "method", "transcript", "definition", "inclusion", "exclusion", "example", "theory", "quote", "rationale", "details", "context", "body"):
        if key in d and d[key] is not None:
            try: d[key] = decrypt(d[key])
            except RuntimeError: pass
    if "languages" in d and isinstance(d["languages"], str):
        try: d["languages"] = json.loads(d["languages"])
        except Exception: pass
    return d

def rows(q, args=()):
    c=conn(); result=[_decode_row(r) for r in c.execute(q,args).fetchall()]; c.close(); return result

def audit(project, event, details, user_id=None):
    c=conn(); c.execute('INSERT INTO audit(project_id,event,details,created_at,user_id) VALUES(?,?,?,?,?)',(project,event,encrypt(json.dumps(details,ensure_ascii=False)),now(),user_id)); c.commit(); c.close()
