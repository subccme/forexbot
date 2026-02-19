"""
core/bot_handlers.py  –  All Telegram command and callback handlers
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, Application
from config.settings import Settings, UserSettings
from config.user_db import UserDB
from config.trade_log import TradeLog
from utils.formatter import (
    fmt_welcome, fmt_status, fmt_trades_list,
    fmt_settings_menu, fmt_help
)
from utils.security import encrypt_key, decrypt_key

logger = logging.getLogger("bot_handlers")


class BotHandlers:
    def __init__(self, settings: Settings, app: Application):
        self.settings = settings
        self.user_db = UserDB(settings.USER_DB_PATH)
        self.trade_log = TradeLog(settings.TRADE_LOG_PATH)

    # ── /start ────────────────────────────────────────────────────────────────

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        cfg = self.user_db.get(user.id)
        if cfg.user_id == 0:
            cfg.user_id = user.id
            self.user_db.save(cfg)
        await update.message.reply_text(
            fmt_welcome(user.first_name),
            parse_mode="Markdown"
        )

    # ── /help ─────────────────────────────────────────────────────────────────

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(fmt_help(), parse_mode="Markdown")

    # ── /connect ──────────────────────────────────────────────────────────────

    async def cmd_connect(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = " ".join(ctx.args) if ctx.args else ""
        parts = text.split()

        if len(parts) < 3:
            await update.message.reply_text(
                "⚙️ *Connect your broker*\n\n"
                "Usage:\n`/connect <broker> <api_key> <account_id>`\n\n"
                "Supported brokers: `oanda`, `alphavantage`\n\n"
                "Example:\n`/connect oanda your-api-key-here 123-456-789`\n\n"
                "⚠️ Your API key is encrypted at rest.",
                parse_mode="Markdown"
            )
            return

        broker, api_key, account_id = parts[0].lower(), parts[1], parts[2]
        uid = update.effective_user.id
        cfg = self.user_db.get(uid)
        cfg.user_id   = uid
        cfg.broker     = broker
        cfg.api_key    = encrypt_key(api_key)
        cfg.account_id = account_id
        cfg.connected  = True
        self.user_db.save(cfg)

        # Delete the message containing the API key for security
        try:
            await update.message.delete()
        except Exception:
            pass

        await ctx.bot.send_message(
            uid,
            f"✅ *Connected!*\nBroker: `{broker}`\nAccount: `{account_id}`\n\n"
            "Your API key is encrypted. Use /settings to configure trading parameters.",
            parse_mode="Markdown"
        )

    # ── /settings ─────────────────────────────────────────────────────────────

    async def cmd_settings(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        cfg = self.user_db.get(uid)
        args = ctx.args

        if not args:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Current Settings", callback_data="settings_view")],
                [
                    InlineKeyboardButton("⚠️ Risk %",      callback_data="set_risk"),
                    InlineKeyboardButton("📦 Lot Size",     callback_data="set_lot"),
                ],
                [
                    InlineKeyboardButton("🛑 Stop Loss",    callback_data="set_sl"),
                    InlineKeyboardButton("🎯 Take Profit",  callback_data="set_tp"),
                ],
                [
                    InlineKeyboardButton("💀 Max Drawdown", callback_data="set_dd"),
                    InlineKeyboardButton("⏱ Scan Interval", callback_data="set_interval"),
                ],
                [InlineKeyboardButton("💱 Currency Pairs", callback_data="set_pairs")],
            ])
            await update.message.reply_text(
                "⚙️ *Settings Panel*\nChoose what to configure:",
                reply_markup=keyboard, parse_mode="Markdown"
            )
            return

        # Direct parameter setting: /settings risk 2.0
        param, *rest = args
        value = " ".join(rest) if rest else ""

        changed = False
        param = param.lower()

        if param == "risk" and value:
            cfg.risk_pct = float(value)
            changed = True
        elif param == "lot" and value:
            cfg.lot_size = float(value)
            changed = True
        elif param == "sl" and value:
            cfg.stop_loss_pips = int(value)
            changed = True
        elif param == "tp" and value:
            cfg.take_profit_pips = int(value)
            changed = True
        elif param == "drawdown" and value:
            cfg.max_drawdown_pct = float(value)
            changed = True
        elif param == "interval" and value:
            cfg.scan_interval_min = int(value)
            changed = True
        elif param == "pairs" and value:
            raw_pairs = [p.strip().upper().replace("/", "_") for p in value.split(",")]
            cfg.pairs = raw_pairs
            changed = True
        elif param == "start":
            cfg.trading_active = True
            changed = True
        elif param == "pause":
            cfg.trading_active = False
            changed = True

        if changed:
            self.user_db.save(cfg)
            await update.message.reply_text(
                f"✅ Setting `{param}` updated!\n\n" + fmt_settings_menu(cfg),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❓ Unknown parameter. Try:\n`/settings risk 2.0`\n"
                "`/settings sl 30`\n`/settings tp 60`\n"
                "`/settings pairs EUR_USD,GBP_USD`",
                parse_mode="Markdown"
            )

    # ── /status ───────────────────────────────────────────────────────────────

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        cfg = self.user_db.get(uid)
        await update.message.reply_text(fmt_status(cfg), parse_mode="Markdown")

    # ── /pause & /resume ──────────────────────────────────────────────────────

    async def cmd_pause(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        cfg = self.user_db.get(uid)
        cfg.trading_active = False
        self.user_db.save(cfg)
        await update.message.reply_text(
            "⏸️ *Trading paused.*\nUse /resume to restart.",
            parse_mode="Markdown"
        )

    async def cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        cfg = self.user_db.get(uid)
        if not cfg.connected:
            await update.message.reply_text(
                "❌ Not connected. Use /connect first.",
                parse_mode="Markdown"
            )
            return
        cfg.trading_active = True
        self.user_db.save(cfg)
        await update.message.reply_text(
            f"▶️ *Trading resumed!*\nMonitoring: {', '.join(cfg.pairs)}\n"
            f"Scan interval: every {cfg.scan_interval_min} minutes.",
            parse_mode="Markdown"
        )

    # ── /stop ─────────────────────────────────────────────────────────────────

    async def cmd_stop_trading(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        cfg = self.user_db.get(uid)
        cfg.trading_active = False
        self.user_db.save(cfg)
        await update.message.reply_text(
            "🛑 *Trading stopped.* All automated orders halted.\n"
            "Open positions remain on broker until manually closed.",
            parse_mode="Markdown"
        )

    # ── /trades ───────────────────────────────────────────────────────────────

    async def cmd_trades(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        trades = self.trade_log.get_user_trades(uid, limit=10)
        await update.message.reply_text(
            fmt_trades_list(trades),
            parse_mode="Markdown"
        )

    # ── /balance ──────────────────────────────────────────────────────────────

    async def cmd_balance(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        cfg = self.user_db.get(uid)
        if not cfg.connected:
            await update.message.reply_text("❌ Not connected. Use /connect first.")
            return

        try:
            from core.price_provider import create_price_provider
            from utils.security import decrypt_key
            provider = create_price_provider(self.settings, cfg.broker)
            if hasattr(provider, "get_account_balance"):
                balance = provider.get_account_balance()
                if balance:
                    await update.message.reply_text(
                        f"💰 *Account Balance*\n`${balance:,.2f}`",
                        parse_mode="Markdown"
                    )
                    return
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")

        await update.message.reply_text(
            "⚠️ Could not fetch balance. Check your broker connection.",
            parse_mode="Markdown"
        )

    # ── Callback handler ──────────────────────────────────────────────────────

    async def handle_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        uid = query.from_user.id
        cfg = self.user_db.get(uid)
        data = query.data

        if data == "settings_view":
            await query.edit_message_text(
                fmt_settings_menu(cfg), parse_mode="Markdown"
            )
        elif data.startswith("set_"):
            prompts = {
                "set_risk":     "Send your risk % per trade (e.g., `1.5`):",
                "set_lot":      "Send lot size (e.g., `0.01`):",
                "set_sl":       "Send stop-loss in pips (e.g., `30`):",
                "set_tp":       "Send take-profit in pips (e.g., `60`):",
                "set_dd":       "Send max drawdown % (e.g., `10`):",
                "set_interval": "Send scan interval in minutes (e.g., `10`):",
                "set_pairs":    "Send pairs comma-separated (e.g., `EUR_USD,GBP_USD,USD_JPY`):",
            }
            ctx.user_data["pending_setting"] = data[4:]
            await query.edit_message_text(
                f"✏️ {prompts.get(data, 'Enter value:')}\n\nType your value in chat.",
                parse_mode="Markdown"
            )

    # ── Generic message handler (for inline setting updates) ──────────────────

    async def handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        pending = ctx.user_data.get("pending_setting")

        if not pending:
            await update.message.reply_text(
                "Use /help to see available commands.",
                parse_mode="Markdown"
            )
            return

        value = update.message.text.strip()
        cfg = self.user_db.get(uid)

        mapping = {
            "risk":     ("risk_pct",          float),
            "lot":      ("lot_size",           float),
            "sl":       ("stop_loss_pips",     int),
            "tp":       ("take_profit_pips",   int),
            "dd":       ("max_drawdown_pct",   float),
            "interval": ("scan_interval_min",  int),
            "pairs":    ("pairs",              lambda v: [p.strip().upper().replace("/","_") for p in v.split(",")]),
        }

        if pending in mapping:
            attr, converter = mapping[pending]
            try:
                setattr(cfg, attr, converter(value))
                self.user_db.save(cfg)
                ctx.user_data.pop("pending_setting", None)
                await update.message.reply_text(
                    f"✅ `{pending}` set to `{value}`\n\n{fmt_settings_menu(cfg)}",
                    parse_mode="Markdown"
                )
            except ValueError:
                await update.message.reply_text(f"❌ Invalid value `{value}`. Try again.")
        else:
            ctx.user_data.pop("pending_setting", None)
            await update.message.reply_text("❓ Unknown setting. Use /settings to try again.")

    # ── Error handler ─────────────────────────────────────────────────────────

    async def error_handler(self, update: object, ctx: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Update {update} caused error: {ctx.error}", exc_info=ctx.error)
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(
                "⚠️ An internal error occurred. Please try again later."
            )
