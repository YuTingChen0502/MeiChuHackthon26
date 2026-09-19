"""Host-owned reference-context bookkeeping shared by analyzer instances.

Backend feature/PCM persistence stays with the registered adapter's cache.
These records contain identities/configuration only; they never accept a baseline.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from analyzers.bundle_validation import read_json, require


class ReferenceContextStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root).resolve() if root is not None else None
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)
        self._records = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(manifest_sha, asset):
        return hashlib.sha256(json.dumps([manifest_sha, asset]).encode()).hexdigest()

    @contextmanager
    def _transaction(self):
        with self._lock:
            fd = None
            lock_path = None
            if self.root:
                lock_path = self.root / ".context-write.lock"
                # Contention or a crash-left lock fails closed; no stale-lock guessing.
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                yield
            finally:
                if fd is not None:
                    os.close(fd)
                    lock_path.unlink()

    def _read(self, key):
        if self.root:
            path = self.root / (key + ".json")
            require(not path.is_symlink(), "Context metadata cannot be a symlink")
            return read_json(path) if path.exists() else None
        return copy.deepcopy(self._records.get(key))

    def _write(self, key, value):
        if self.root:
            path = self.root / (key + ".json")
            temporary = self.root / (key + "." + uuid4().hex + ".tmp")
            try:
                with temporary.open("x", encoding="utf-8") as handle:
                    json.dump(value, handle, allow_nan=False)
                os.replace(temporary, path)
            finally:
                if temporary.exists():
                    temporary.unlink()
        else:
            self._records[key] = copy.deepcopy(value)

    def add(self, manifest_sha, asset, config, window_ids):
        key = self._key(manifest_sha, asset)
        with self._transaction():
            require(self._read(key) is None, "Reference context identity must not be reused")
            self._write(key, {
                "manifest_sha256": manifest_sha, "context_asset": asset,
                "config": config, "window_ids": list(window_ids), "target": None,
            })

    def lookup_and_bind(self, manifest_sha, asset, config, target):
        key = self._key(manifest_sha, asset)
        with self._transaction():
            record = self._read(key)
            if record is None:
                return None, "reference_context_unavailable"
            require(record.get("manifest_sha256") == manifest_sha and record.get("context_asset") == asset,
                    "Context cache identity mismatch")
            if record["config"] != config:
                return None, "reference_configuration_mismatch"
            if record["target"] is not None and record["target"] != target:
                return None, "reference_target_binding_mismatch"
            if record["target"] is None:
                record["target"] = copy.deepcopy(target)
                self._write(key, record)
            return copy.deepcopy(record), None
