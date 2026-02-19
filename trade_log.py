"""
config/trade_log.py  –  Append-only JSON trade journal
"""

import json
import os
import threading
from datetime import datetime
from typing import List, Dict


class TradeLog:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._records: List[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                self._records = json.load(f)

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self._records, f, indent=2)

    def log(self, user_id: int, trade: dict):
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "user_id": user_id,
            **trade
        }
        with self._lock:
            self._records.append(entry)
            self._save()
        return entry

    def get_user_trades(self, user_id: int, limit: int = 10) -> List[dict]:
        with self._lock:
            user = [r for r in self._records if r.get("user_id") == user_id]
        return user[-limit:]
