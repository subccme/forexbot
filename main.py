"""
ForexBot - Automated Forex Trading via Telegram
Main entry point
"""

import asyncio
import logging
import signal
import sys
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler, filters
)
from config.settings import Settings
from core.bot_handlers import BotHandlers
from core.scheduler import TradingScheduler
from utils.logger import setup_logger

logger = setup_logger("main")

def main():
    settings = Settings()
    settings.validate()

    logger.info("🚀 Starting ForexBot...")

    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    handlers = BotHandlers(settings, app)
    scheduler = TradingScheduler(settings, app.bot)

    # Register command handlers
    app.add_handler(CommandHandler("start",   handlers.cmd_start))
    app.add_handler(CommandHandler("connect", handlers.cmd_connect))
    app.add_handler(CommandHandler("settings",handlers.cmd_settings))
    app.add_handler(CommandHandler("status",  handlers.cmd_status))
    app.add_handler(CommandHandler("pause",   handlers.cmd_pause))
    app.add_handler(CommandHandler("resume",  handlers.cmd_resume))
    app.add_handler(CommandHandler("trades",  handlers.cmd_trades))
    app.add_handler(CommandHandler("balance", handlers.cmd_balance))
    app.add_handler(CommandHandler("help",    handlers.cmd_help))
    app.add_handler(CommandHandler("stop",    handlers.cmd_stop_trading))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(handlers.handle_callback))

    # Generic message fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    # Error handler
    app.add_error_handler(handlers.error_handler)

    # Start the scheduler in background
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler.run())

    logger.info("✅ ForexBot is live. Listening for commands...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
