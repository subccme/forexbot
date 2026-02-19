"""
utils/formatter.py  –  Telegram message formatters
"""

from datetime import datetime
from config.settings import UserSettings


def fmt_welcome(name: str) -> str:
    return (
        f"👋 Welcome, *{name}*!\n\n"
        "🤖 *ForexBot* — AI-powered automated Forex trading\n\n"
        "I monitor markets 24/7 using real-time web research and technical analysis, "
        "then execute trades automatically on your behalf.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 *Quick Start*\n"
        "1️⃣ /connect — Link your broker account\n"
        "2️⃣ /settings — Configure risk & pairs\n"
        "3️⃣ /resume — Start automated trading\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Type /help for all commands."
    )


def fmt_help() -> str:
    return (
        "📖 *ForexBot Commands*\n\n"
        "/start — Initialize bot\n"
        "/connect `<broker> <api_key> <account_id>` — Link broker\n"
        "/settings — Open settings panel (interactive)\n"
        "/settings `risk 2.0` — Set risk % directly\n"
        "/settings `sl 30` — Set stop-loss pips\n"
        "/settings `tp 60` — Set take-profit pips\n"
        "/settings `pairs EUR_USD,GBP_USD` — Set pairs\n"
        "/settings `drawdown 10` — Max drawdown %\n"
        "/settings `interval 10` — Scan every N minutes\n"
        "/status — View connection & trading status\n"
        "/balance — Check broker account balance\n"
        "/trades — Show last 10 executed trades\n"
        "/resume — Start automated trading\n"
        "/pause — Pause trading (keeps positions open)\n"
        "/stop — Stop trading completely\n"
        "/help — Show this message\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *Supported Brokers*\n"
        "`oanda` — OANDA (live + paper)\n"
        "`alphavantage` — Alpha Vantage (data only)\n\n"
        "⚠️ Forex trading carries significant risk. Only trade what you can afford to lose."
    )


def fmt_settings_menu(cfg: UserSettings) -> str:
    status = "🟢 Active" if cfg.trading_active else "🔴 Paused"
    connected = "✅ Connected" if cfg.connected else "❌ Not connected"
    pairs = ", ".join(cfg.pairs) if cfg.pairs else "None set"
    return (
        f"⚙️ *Current Settings*\n\n"
        f"🔗 Broker: `{cfg.broker or 'not set'}` {connected}\n"
        f"📊 Status: {status}\n"
        f"💱 Pairs: `{pairs}`\n\n"
        f"💼 Risk per trade: `{cfg.risk_pct}%`\n"
        f"📦 Lot size: `{cfg.lot_size}`\n"
        f"🛑 Stop-loss: `{cfg.stop_loss_pips} pips`\n"
        f"🎯 Take-profit: `{cfg.take_profit_pips} pips`\n"
        f"💀 Max drawdown: `{cfg.max_drawdown_pct}%`\n"
        f"⏱ Scan interval: `every {cfg.scan_interval_min} min`\n\n"
        "Use `/settings <param> <value>` to change any setting."
    )


def fmt_status(cfg: UserSettings) -> str:
    status = "🟢 ACTIVE" if cfg.trading_active else "🔴 PAUSED"
    connected = "✅ Connected" if cfg.connected else "❌ Not connected"
    pairs = ", ".join(cfg.pairs) if cfg.pairs else "None"
    return (
        f"📡 *Bot Status*\n\n"
        f"🔗 Broker: `{cfg.broker or 'Not set'}` {connected}\n"
        f"📊 Trading: {status}\n"
        f"💱 Watching: `{pairs}`\n"
        f"💀 Drawdown limit: `{cfg.max_drawdown_pct}%`\n"
        f"⏱ Analysis: every `{cfg.scan_interval_min}` minutes\n"
    )


def fmt_trade_alert(trade: dict, price_data) -> str:
    d = trade.get("direction", "")
    emoji = "📈" if d == "BUY" else "📉"
    reasons = "\n".join(f"  • {r}" for r in trade.get("reasons", [])[:3])
    return (
        f"{emoji} *Trade Executed*\n\n"
        f"Pair:        `{trade.get('pair')}`\n"
        f"Direction:   *{d}*\n"
        f"Units:       `{trade.get('units'):,}`\n"
        f"Price:       `{trade.get('price'):.5f}`\n"
        f"Stop-Loss:   `{trade.get('sl'):.5f}`\n"
        f"Take-Profit: `{trade.get('tp'):.5f}`\n"
        f"Confidence:  `{trade.get('confidence', 0):.0%}`\n\n"
        f"📰 *Signals*\n{reasons or '  • Web sentiment analysis'}\n\n"
        f"🕐 `{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}`"
    )


def fmt_drawdown_alert(message: str) -> str:
    return (
        f"🚨 *DRAWDOWN LIMIT REACHED*\n\n"
        f"{message}\n\n"
        "Trading has been automatically halted to protect your account.\n"
        "Use /resume to restart (after reviewing your risk settings)."
    )


def fmt_trades_list(trades: list) -> str:
    if not trades:
        return "📭 No trades recorded yet."
    lines = ["📋 *Recent Trades*\n"]
    for t in reversed(trades[-10:]):
        ts = t.get("ts", "")[:16]
        d  = t.get("direction", "?")
        emoji = "📈" if d == "BUY" else "📉"
        lines.append(
            f"{emoji} `{t.get('pair')}` {d} @ `{t.get('price', 0):.5f}` "
            f"— conf `{t.get('confidence', 0):.0%}` — {ts}"
        )
    return "\n".join(lines)
