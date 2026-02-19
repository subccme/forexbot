"""
config/user_db.py  –  Lightweight JSON user store
"""

import json
import os
import threading
from typing import Optional, Dict
from config.settings import UserSettings


class UserDB:
    """Thread-safe JSON-backed user settings store."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._data: Dict[int, dict] = {}
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                raw = json.load(f)
            self._data = {int(k): v for k, v in raw.items()}

    def _save(self):
        with open(self.path, "w") as f:
            json.dump({str(k): v for k, v in self._data.items()}, f, indent=2)

    # ── Public API ───────────────────────────────────────────────────────

    def get(self, user_id: int) -> UserSettings:
        with self._lock:
            raw = self._data.get(user_id)
            if raw:
                return UserSettings.from_dict(raw)
            return UserSettings(user_id=user_id)

    def save(self, settings: UserSettings):
        with self._lock:
            self._data[settings.user_id] = settings.to_dict()
            self._save()

    def all_active(self):
        """Yield UserSettings for every user with trading_active=True."""
        with self._lock:
            for uid, raw in self._data.items():
                s = UserSettings.from_dict(raw)
                if s.trading_active and s.connected:
                    yield s

    def delete(self, user_id: int):
        with self._lock:
            self._data.pop(user_id, None)
            self._save()
