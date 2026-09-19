"""Single-file SQLite durability for RuntimeAPI identities, sessions, and commands."""

from __future__ import annotations

import copy
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from threading import RLock


def _encode(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decode(value: str | None):
    return None if value is None else json.loads(value)


class SQLiteRuntimeStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;
                CREATE TABLE IF NOT EXISTS runtime_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS commands (
                    session_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    command_text TEXT NOT NULL,
                    response TEXT NOT NULL,
                    PRIMARY KEY (session_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS baselines (
                    baseline_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    profile TEXT NOT NULL,
                    PRIMARY KEY (baseline_id, version)
                );
                """
            )

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _persist_baseline(connection, session_state: dict) -> None:
        profiles = session_state.get("baseline_records")
        if profiles is None:
            current = session_state.get("baseline")
            profiles = [] if current is None else [current]
        for profile in profiles:
            encoded = _encode(profile)
            row = connection.execute(
                "SELECT profile FROM baselines WHERE baseline_id=? AND version=?",
                (profile["baseline_id"], profile["version"]),
            ).fetchone()
            if row is not None and row[0] != encoded:
                raise ValueError("immutable baseline identity already stores different content")
            connection.execute(
                "INSERT OR IGNORE INTO baselines(baseline_id, version, profile) VALUES(?,?,?)",
                (profile["baseline_id"], profile["version"], encoded),
            )

    def load_runtime_state(self) -> dict | None:
        with self.lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM runtime_state WHERE singleton=1"
            ).fetchone()
        return copy.deepcopy(_decode(row[0]) if row else None)

    def save_runtime_state(self, state: dict) -> None:
        with self.lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO runtime_state(singleton,payload) VALUES(1,?) "
                "ON CONFLICT(singleton) DO UPDATE SET payload=excluded.payload",
                (_encode(state),),
            )
            connection.commit()

    def save_runtime_and_session(self, runtime_state: dict, session_state: dict) -> None:
        with self.lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO runtime_state(singleton,payload) VALUES(1,?) "
                "ON CONFLICT(singleton) DO UPDATE SET payload=excluded.payload",
                (_encode(runtime_state),),
            )
            connection.execute(
                "INSERT INTO sessions(session_id,payload) VALUES(?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload",
                (session_state["session_id"], _encode(session_state)),
            )
            self._persist_baseline(connection, session_state)
            connection.commit()

    def save_session(self, state: dict) -> None:
        with self.lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO sessions(session_id,payload) VALUES(?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload",
                (state["session_id"], _encode(state)),
            )
            self._persist_baseline(connection, state)
            connection.commit()

    def load_sessions(self) -> list[dict]:
        with self.lock, closing(self._connect()) as connection:
            rows = connection.execute("SELECT payload FROM sessions ORDER BY session_id").fetchall()
        return [_decode(row[0]) for row in rows]

    def get_command(self, session_id: str, idempotency_key: str) -> dict | None:
        with self.lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT command_text,response FROM commands WHERE session_id=? AND idempotency_key=?",
                (session_id, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        return {"command": row[0], "response": _decode(row[1])}

    def record_command(
        self,
        *,
        session_id: str,
        idempotency_key: str,
        command_text: str,
        response: dict,
        session_state: dict,
    ) -> None:
        with self.lock, closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT command_text,response FROM commands WHERE session_id=? AND idempotency_key=?",
                (session_id, idempotency_key),
            ).fetchone()
            encoded_response = _encode(response)
            if existing is not None:
                if existing != (command_text, encoded_response):
                    raise ValueError("idempotency key already stores different content")
                connection.rollback()
                return
            connection.execute(
                "INSERT INTO commands(session_id,idempotency_key,command_text,response) VALUES(?,?,?,?)",
                (session_id, idempotency_key, command_text, encoded_response),
            )
            connection.execute(
                "INSERT INTO sessions(session_id,payload) VALUES(?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload",
                (session_id, _encode(session_state)),
            )
            self._persist_baseline(connection, session_state)
            connection.commit()


class SQLiteCommandLedger:
    def __init__(self, store: SQLiteRuntimeStore, session_id: str) -> None:
        self.store = store
        self.session_id = session_id
        self.lock = store.lock

    def get(self, session_id: str, idempotency_key: str) -> dict | None:
        return self.store.get_command(session_id, idempotency_key)

    def put(
        self,
        session_id: str,
        idempotency_key: str,
        command_text: str,
        response: dict,
        *,
        session_state: dict,
    ) -> None:
        self.store.record_command(
            session_id=session_id,
            idempotency_key=idempotency_key,
            command_text=command_text,
            response=response,
            session_state=session_state,
        )

    def latest_session_state(self) -> dict | None:
        states = [state for state in self.store.load_sessions() if state["session_id"] == self.session_id]
        return states[0] if states else None
