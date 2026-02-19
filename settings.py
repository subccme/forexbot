"""
config/settings.py  –  Central configuration and environment loader
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class UserSettings:
    """Per-user trading preferences stored in JSON."""
    user_id: int = 0
    broker: str = ""                  # "oanda" | "mt4" | "mt5" | "ctrader"
    api_key: str = ""
    account_id: str = ""
    pairs: List[str] = field(default_factory=lambda: ["EUR_USD", "GBP_USD", "USD_JPY"])
    risk_pct: float = 1.0             # % of balance per trade
    lot_size: float = 0.01
    stop_loss_pips: int = 30
    take_profit_pips: int = 60
    max_drawdown_pct: float = 10.0    # halt trading if hit
    scan_interval_min: int = 10       # minutes between analysis cycles
    trading_active: bool = False
    connected: bool = False
    balance_at_start: float = 0.0
    current_balance: float = 0.0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class Settings:
    """Global application settings loaded from environment variables."""

    # ── Telegram ────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # ── Price providers ─────────────────────────────────────────────────
    OANDA_API_KEY: str      = os.getenv("OANDA_API_KEY", "")
    OANDA_ACCOUNT_ID: str   = os.getenv("OANDA_ACCOUNT_ID", "")
    OANDA_BASE_URL: str     = os.getenv("OANDA_BASE_URL", "https://api-fxtrade.oanda.com/v3")
    # Practice: https://api-fxpractice.oanda.com/v3

    ALPHA_VANTAGE_KEY: str  = os.getenv("ALPHA_VANTAGE_KEY", "")

    # ── Web search (SerpAPI or Google Custom Search) ─────────────────────
    SERP_API_KEY: str          = os.getenv("SERP_API_KEY", "")
    GOOGLE_CSE_KEY: str        = os.getenv("GOOGLE_CSE_KEY", "")
    GOOGLE_CSE_ID: str         = os.getenv("GOOGLE_CSE_ID", "")

    # ── Storage ──────────────────────────────────────────────────────────
    USER_DB_PATH: str = os.getenv("USER_DB_PATH", "data/users.json")
    TRADE_LOG_PATH: str = os.getenv("TRADE_LOG_PATH", "data/trades.json")

    # ── Safety ───────────────────────────────────────────────────────────
    MAX_OPEN_TRADES: int = int(os.getenv("MAX_OPEN_TRADES", "5"))
    DEFAULT_SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL_MIN", "10"))

    def validate(self):
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN is not set in .env")
        if not (self.SERP_API_KEY or self.GOOGLE_CSE_KEY):
            raise ValueError("❌ At least one web-search API key is required (SERP_API_KEY or GOOGLE_CSE_KEY)")
        # Ensure data directory
        os.makedirs(os.path.dirname(self.USER_DB_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(self.TRADE_LOG_PATH), exist_ok=True)
