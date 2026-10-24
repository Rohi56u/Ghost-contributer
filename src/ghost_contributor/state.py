from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .errors import SafeStop


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".ghost-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def process_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SafeStop("busy", "Another Ghost operation is active; try later.") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class State:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "state.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, repo TEXT NOT NULL, period TEXT NOT NULL,
                    status TEXT NOT NULL, created TEXT NOT NULL, detail TEXT NOT NULL,
                    UNIQUE(repo, period));
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY, repo TEXT NOT NULL, status TEXT NOT NULL,
                    created TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS flags (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
                    previous TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
                    BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
                    BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
            """)
        os.chmod(self.path, 0o600)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def lock(self):
        return process_lock(self.root / "operation.lock")

    def audit(self, action: str, **detail):
        # Call sites pass identifiers, digests and controlled error codes, never prompts.
        event = json.dumps({"at": now(), "action": action, **detail}, sort_keys=True, ensure_ascii=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT digest FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            previous = row[0] if row else "0" * 64
            sha = hashlib.sha256((previous + event).encode()).hexdigest()
            db.execute("INSERT INTO audit(event, previous, digest) VALUES(?,?,?)", (event, previous, sha))

    def verify_audit(self) -> int:
        previous, count = "0" * 64, 0
        with self.connect() as db:
            for row in db.execute("SELECT * FROM audit ORDER BY seq"):
                expected = hashlib.sha256((previous + row["event"]).encode()).hexdigest()
                if row["previous"] != previous or row["digest"] != expected:
                    raise SafeStop("audit_integrity", "Audit hash-chain verification failed.")
                previous, count = expected, count + 1
        return count

    def flag(self, key: str) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT value FROM flags WHERE key=?", (key,)).fetchone()
            return bool(row and row[0] == "1")

    def set_flag(self, key: str, value: bool):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO flags VALUES(?,?)", (key, "1" if value else "0"))
        self.audit("control", control=key, enabled=value)

    def guard(self):
        if self.flag("killed") or self.flag("paused"):
            raise SafeStop("paused", "Ghost is paused or stopped; explicitly resume before new work.")

    def reserve_run(self, run_id: str, repo: str, period: str) -> bool:
        with self.connect() as db:
            result = db.execute("INSERT OR IGNORE INTO runs VALUES(?,?,?,?,?,?)", (run_id, repo, period, "running", now(), "started"))
            return result.rowcount == 1

    def finish_run(self, run_id: str, status: str, detail: str):
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?, detail=? WHERE id=?", (status, detail, run_id))
        self.audit("run_finished", run=run_id, status=status, reason=detail)

    def put(self, proposal: dict, status: str = "pending"):
        with self.connect() as db:
            db.execute("INSERT INTO proposals VALUES(?,?,?,?,?)", (proposal["id"], proposal["repo"], status, now(), json.dumps(proposal)))

    def get(self, proposal_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM proposals ORDER BY created DESC LIMIT 1").fetchone() if proposal_id == "latest" else db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if not row:
            raise SafeStop("not_found", "No matching proposal exists.")
        return {**json.loads(row["payload"]), "status": row["status"], "created": row["created"]}

    def update(self, proposal_id: str, status: str, **changes):
        p = self.get(proposal_id)
        p.update(changes)
        p.pop("status", None)
        p.pop("created", None)
        with self.connect() as db:
            db.execute("UPDATE proposals SET status=?, payload=? WHERE id=?", (status, json.dumps(p), p["id"]))

    def list_proposals(self) -> list[dict]:
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM proposals ORDER BY created DESC LIMIT 100")]
        return [self.get(p) for p in ids]

    def has_pending(self, repo: str) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM proposals WHERE repo=? AND status IN ('pending','committing','commit_failed','push_unknown')", (repo,)).fetchone() is not None

    def handled_targets(self, repo: str, base: str) -> set[tuple[str, str]]:
        with self.connect() as db:
            proposals = [json.loads(r[0]) for r in db.execute("SELECT payload FROM proposals WHERE repo=?", (repo,))]
        return {(p["target"]["path"], p["target"]["symbol"]) for p in proposals if p["base_sha"] == base}

    def runs(self) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM runs ORDER BY created DESC LIMIT 100")]

    def events(self) -> list[dict]:
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT event FROM audit ORDER BY seq DESC LIMIT 100")]
