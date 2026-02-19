"""
core/scheduler.py  –  Async background scheduler
Runs analysis + execution cycles for all active users every N minutes.
"""

import asyncio
import logging
from datetime import datetime, timezone
from telegram import Bot
from config.settings import Settings
from config.user_db import UserDB
from config.trade_log import TradeLog
from analysis.web_analyst import WebAnalyst
from analysis.technicals import technical_signal
from core.price_provider import create_price_provider
from trading.executor import TradeExecutor
from utils.formatter import fmt_trade_alert, fmt_drawdown_alert

logger = logging.getLogger("scheduler")


class TradingScheduler:
    def __init__(self, settings: Settings, bot: Bot):
        self.settings = settings
        self.bot = bot
        self.user_db = UserDB(settings.USER_DB_PATH)
        self.trade_log = TradeLog(settings.TRADE_LOG_PATH)
        self.analyst = WebAnalyst(settings)
        self.executor = TradeExecutor(self.trade_log)

    async def run(self):
        logger.info("⏰ Scheduler started")
        while True:
            try:
                await self._cycle()
            except Exception as e:
                logger.error(f"Scheduler cycle error: {e}", exc_info=True)
            await asyncio.sleep(60)   # wake up every 60s, inner logic checks interval

    async def _cycle(self):
        now_min = datetime.now(timezone.utc).minute
        for user_cfg in self.user_db.all_active():
            # Check if this user's interval has elapsed
            interval = user_cfg.scan_interval_min
            if now_min % interval != 0:
                continue

            logger.info(f"📊 Running analysis cycle for user {user_cfg.user_id}")
            try:
                await self._process_user(user_cfg)
            except Exception as e:
                logger.error(f"Error processing user {user_cfg.user_id}: {e}")

    async def _process_user(self, user_cfg):
        provider = create_price_provider(self.settings, user_cfg.broker)

        for pair in user_cfg.pairs:
            try:
                # 1. Fetch live price
                price_data = provider.get_price(pair)
                if not price_data:
                    logger.warning(f"No price data for {pair}")
                    continue

                # 2. Web-based analysis
                signal = self.analyst.analyse(pair)

                # 3. Candle data for technicals
                candles = []
                if hasattr(provider, "get_candles"):
                    candles = provider.get_candles(pair, "H1", 60)

                # 4. Execute if signal qualifies
                result = self.executor.evaluate_and_execute(
                    web_signal=signal,
                    candles=candles,
                    user_settings=user_cfg,
                    price_data=price_data,
                    broker_provider=provider
                )

                # 5. Notify user
                if result:
                    if result.get("type") == "DRAWDOWN_HALT":
                        user_cfg.trading_active = False
                        self.user_db.save(user_cfg)
                        msg = fmt_drawdown_alert(result["message"])
                        await self.bot.send_message(user_cfg.user_id, msg, parse_mode="Markdown")
                    elif result.get("type") == "TRADE":
                        msg = fmt_trade_alert(result, price_data)
                        await self.bot.send_message(user_cfg.user_id, msg, parse_mode="Markdown")

                # 6. Always send signal summary even if no trade
                elif signal.direction != "HOLD":
                    summary = signal.summary()
                    await self.bot.send_message(
                        user_cfg.user_id,
                        f"📡 *Market Signal (no trade — below threshold)*\n{summary}",
                        parse_mode="Markdown"
                    )

                await asyncio.sleep(2)   # small gap between pairs

            except Exception as e:
                logger.error(f"Error on {pair} for user {user_cfg.user_id}: {e}")
                await asyncio.sleep(5)
