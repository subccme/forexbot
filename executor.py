"""
trading/executor.py  –  Trade execution engine

Combines web sentiment + technical signal → decides whether to trade.
Manages risk: lot sizing, SL/TP calculation, drawdown limits.
"""

import logging
from typing import Optional, Tuple, Dict
from config.settings import UserSettings
from config.trade_log import TradeLog
from analysis.web_analyst import TradeSignal
from analysis.technicals import technical_signal, atr, support_resistance

logger = logging.getLogger("executor")


# ─────────────────────────────────────────────────────────────────────────────
# pip value helpers
# ─────────────────────────────────────────────────────────────────────────────

def pip_size(pair: str) -> float:
    return 0.01 if "JPY" in pair else 0.0001

def pips_to_price(pips: int, pair: str) -> float:
    return pips * pip_size(pair)


# ─────────────────────────────────────────────────────────────────────────────
# Executor
# ─────────────────────────────────────────────────────────────────────────────

class TradeExecutor:
    """
    Decides whether to enter a trade based on combined signals,
    computes position sizing, SL/TP, and submits to the broker.
    """

    # Minimum combined confidence to trade
    MIN_COMBINED_CONFIDENCE = 0.45

    def __init__(self, trade_log: TradeLog):
        self.trade_log = trade_log

    # ── Risk calculations ─────────────────────────────────────────────────────

    def compute_units(self, balance: float, risk_pct: float,
                      sl_pips: int, pair: str) -> int:
        """
        Units = (balance * risk_pct/100) / (sl_pips * pip_size)
        For OANDA, 1 unit of EUR_USD ≈ $1 face value.
        Adjust for account currency as needed.
        """
        risk_amount = balance * (risk_pct / 100)
        sl_price = sl_pips * pip_size(pair)
        if sl_price == 0:
            return 1000
        units = int(risk_amount / sl_price)
        return max(units, 1000)   # minimum 1 micro-lot = 1000 units

    def compute_sl_tp(self, price: float, direction: str,
                      sl_pips: int, tp_pips: int, pair: str,
                      candles: list = None) -> Tuple[float, float]:
        """Compute SL and TP prices. Optionally use ATR-based SL."""
        pip = pip_size(pair)
        if candles and len(candles) >= 15:
            atr_val = atr(candles)
            if atr_val:
                sl_pips = max(sl_pips, int(atr_val / pip * 1.5))
                tp_pips = max(tp_pips, int(atr_val / pip * 3.0))

        if direction == "BUY":
            sl = round(price - sl_pips * pip, 5)
            tp = round(price + tp_pips * pip, 5)
        else:
            sl = round(price + sl_pips * pip, 5)
            tp = round(price - tp_pips * pip, 5)
        return sl, tp

    # ── Drawdown guard ────────────────────────────────────────────────────────

    def check_drawdown(self, user_settings: UserSettings,
                       current_balance: float) -> bool:
        """Return True if within safe drawdown, False if limit breached."""
        start = user_settings.balance_at_start
        if start <= 0:
            return True
        drawdown_pct = (start - current_balance) / start * 100
        if drawdown_pct >= user_settings.max_drawdown_pct:
            logger.warning(
                f"User {user_settings.user_id}: drawdown {drawdown_pct:.1f}% "
                f"≥ limit {user_settings.max_drawdown_pct}% → halting"
            )
            return False
        return True

    # ── Combined signal logic ────────────────────────────────────────────────

    def combined_direction(self, web_signal: TradeSignal,
                           tech: Dict) -> Tuple[str, float]:
        """
        Merge web sentiment and technical bias.
        Returns (direction, combined_confidence).
        """
        web_dir  = web_signal.direction      # BUY | SELL | HOLD
        tech_dir = tech.get("bias", "HOLD")  # BUY | SELL | HOLD
        web_conf = web_signal.confidence

        # Tech score normalised to 0-1 (max ±7)
        tech_conf = min(abs(tech.get("score", 0)) / 7.0, 1.0)

        if web_dir == "HOLD" and tech_dir == "HOLD":
            return "HOLD", 0.0

        # Both agree → high confidence
        if web_dir == tech_dir and web_dir != "HOLD":
            combined = (web_conf * 0.6 + tech_conf * 0.4)
            return web_dir, combined

        # Disagree → follow the stronger signal with lower confidence
        if web_dir != "HOLD" and tech_dir == "HOLD":
            return web_dir, web_conf * 0.7
        if tech_dir != "HOLD" and web_dir == "HOLD":
            return tech_dir, tech_conf * 0.6

        # Opposite signals → no trade
        return "HOLD", 0.0

    # ── Main execute function ─────────────────────────────────────────────────

    def evaluate_and_execute(self,
                              web_signal: TradeSignal,
                              candles: list,
                              user_settings: UserSettings,
                              price_data,
                              broker_provider) -> Optional[dict]:
        """
        Evaluates signals and executes a trade if conditions are met.
        Returns a trade record dict or None.
        """
        pair = web_signal.pair

        # Technical analysis
        tech = technical_signal(candles)
        direction, confidence = self.combined_direction(web_signal, tech)

        logger.info(
            f"{pair}: web={web_signal.direction}({web_signal.confidence:.0%}) "
            f"tech={tech['bias']}({tech['score']}) "
            f"→ {direction} ({confidence:.0%})"
        )

        if direction == "HOLD" or confidence < self.MIN_COMBINED_CONFIDENCE:
            logger.info(f"  ↳ No trade: confidence {confidence:.0%} below threshold")
            return None

        # Drawdown guard
        current_balance = price_data.mid   # placeholder; real balance fetched below
        if hasattr(broker_provider, "get_account_balance"):
            bal = broker_provider.get_account_balance()
            if bal:
                current_balance = bal

        if not self.check_drawdown(user_settings, current_balance):
            return {
                "type": "DRAWDOWN_HALT",
                "pair": pair,
                "message": "Max drawdown reached — trading halted automatically"
            }

        # Compute position
        price = price_data.bid if direction == "SELL" else price_data.ask
        units = self.compute_units(
            current_balance,
            user_settings.risk_pct,
            user_settings.stop_loss_pips,
            pair
        )
        sl, tp = self.compute_sl_tp(
            price, direction,
            user_settings.stop_loss_pips,
            user_settings.take_profit_pips,
            pair, candles
        )

        logger.info(f"  ↳ {direction} {units} units @ {price:.5f} SL={sl} TP={tp}")

        # Submit order
        result = broker_provider.place_order(
            pair=pair,
            side=direction.lower(),
            units=units,
            sl_price=sl,
            tp_price=tp
        )

        if result is None:
            logger.error(f"  ↳ Order submission failed")
            return None

        trade_record = {
            "type": "TRADE",
            "pair": pair,
            "direction": direction,
            "units": units,
            "price": price,
            "sl": sl,
            "tp": tp,
            "confidence": round(confidence, 3),
            "web_score": round(web_signal.raw_score, 3),
            "tech_score": tech.get("score", 0),
            "reasons": web_signal.reasons[:3] + [tech.get("details", "")[:100]],
            "broker_result": str(result)[:200]
        }

        self.trade_log.log(user_settings.user_id, trade_record)
        logger.info(f"  ✅ Trade logged")
        return trade_record
