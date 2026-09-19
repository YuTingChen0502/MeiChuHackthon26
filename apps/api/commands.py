"""Transactional command handling with durable idempotency responses."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from jsonschema import ValidationError

from core.contracts.validation import WIRE, validate_record, validate_response
from roles.pa.session import SessionCommandError, canonical_command


class JsonCommandLedger:
    """Small restart-safe ledger; each rewrite is atomic on the local filesystem."""

    _registry_guard = RLock()
    _path_locks: dict[str, RLock] = {}

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        identity = str(self.path.resolve())
        with self._registry_guard:
            self._lock = self._path_locks.setdefault(identity, RLock())
        self.lock = self._lock
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"entries": {}, "session_state": None})

    def _read(self) -> dict:
        document = json.loads(self.path.read_text(encoding="utf-8"))
        if "entries" not in document:
            document = {"entries": document, "session_state": None}
        return document

    def _write(self, value: dict) -> None:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        descriptor, temporary = tempfile.mkstemp(prefix=self.path.name, suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _key(session_id: str, idempotency_key: str) -> str:
        return f"{session_id}\u0000{idempotency_key}"

    def get(self, session_id: str, idempotency_key: str) -> dict | None:
        with self._lock:
            result = self._read()["entries"].get(self._key(session_id, idempotency_key))
        return copy.deepcopy(result)

    def put(
        self,
        session_id: str,
        idempotency_key: str,
        command_text: str,
        response: dict,
        *,
        session_state: dict,
    ) -> None:
        key = self._key(session_id, idempotency_key)
        with self._lock:
            document = self._read()
            records = document["entries"]
            if key in records:
                if records[key]["command"] != command_text or records[key]["response"] != response:
                    raise RuntimeError("idempotency ledger entry changed during serialization")
                return
            records[key] = {"command": command_text, "response": copy.deepcopy(response)}
            document["session_state"] = copy.deepcopy(session_state)
            self._write(document)

    def latest_session_state(self) -> dict | None:
        with self._lock:
            return copy.deepcopy(self._read()["session_state"])


class CommandHandler:
    def __init__(self, *, session, ledger) -> None:
        self.session = session
        self.ledger = ledger
        self._lock = RLock()

    @staticmethod
    def _rejected(command: dict, session, *, status: int, code: str, message: str, retryable: bool) -> dict:
        response = {
            "record_type": "CommandResponse",
            "schema_version": "1.0",
            "session_id": command["session_id"],
            "idempotency_key": command["idempotency_key"],
            "outcome": "rejected",
            "http_status": status,
            "snapshot": session.snapshot(),
            "error": {"code": code, "message": message, "retryable": retryable},
        }
        validate_response(response)
        return response

    def handle(self, command: dict) -> dict:
        # A malformed transport body without a usable envelope belongs to the HTTP
        # framework. This handler intentionally requires the ledger identity fields.
        if not isinstance(command, dict) or not command.get("session_id") or not command.get("idempotency_key"):
            raise ValueError("command lacks a usable session/idempotency envelope")
        command_text = canonical_command(command)
        # Every Runtime writer uses session -> durable-store lock order. Holding the
        # session lock through commit/rollback prevents snapshots from observing an
        # uncommitted command version.
        with self._lock, self.session.command_transaction(), self.ledger.lock:
            existing = self.ledger.get(command["session_id"], command["idempotency_key"])
            if existing is not None:
                if existing["command"] == command_text:
                    return copy.deepcopy(existing["response"])
                return self._rejected(
                    command,
                    self.session,
                    status=409,
                    code="idempotency_conflict",
                    message="Idempotency key was already used for different content.",
                    retryable=False,
                )
            pre_state = self.session.export_state()
            try:
                validate_record(command, WIRE, "SessionCommand")
                snapshot = self.session.apply_command(command)
                response = {
                    "record_type": "CommandResponse",
                    "schema_version": "1.0",
                    "session_id": command["session_id"],
                    "idempotency_key": command["idempotency_key"],
                    "outcome": "applied",
                    "http_status": 200,
                    "snapshot": snapshot,
                    "error": None,
                }
            except ValidationError as exc:
                self.session.restore_state(pre_state)
                response = self._rejected(
                    command,
                    self.session,
                    status=422,
                    code="invalid_payload",
                    message=exc.message,
                    retryable=False,
                )
            except ValueError as exc:
                self.session.restore_state(pre_state)
                response = self._rejected(
                    command,
                    self.session,
                    status=422,
                    code="invalid_payload",
                    message=str(exc),
                    retryable=False,
                )
            except SessionCommandError as exc:
                self.session.restore_state(pre_state)
                response = self._rejected(
                    command,
                    self.session,
                    status=exc.http_status,
                    code=exc.code,
                    message=str(exc),
                    retryable=exc.retryable,
                )
            validate_response(response)
            try:
                self.ledger.put(
                    command["session_id"],
                    command["idempotency_key"],
                    command_text,
                    response,
                    session_state=self.session.export_state(),
                )
            except Exception:
                self.session.restore_state(pre_state)
                raise
            return copy.deepcopy(response)
