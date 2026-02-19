"""
analysis/technicals.py  –  Lightweight technical indicators from OHLCV candles.

Used as a secondary confirmation layer alongside web sentiment.
No external ML models — pure price-action math.
"""

from typing import List, Optional, Dict, Tuple
import math


def _closes(candles: list) -> List[float]:
    return [c["close"] for c in candles]

def _highs(candles: list) -> List[float]:
    return [c["high"] for c in candles]

def _lows(candles: list) -> List[float]:
    return [c["low"] for c in candles]


# ── Moving averages ───────────────────────────────────────────────────────────

def ema(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result

def sma(values: List[float], period: int) -> List[float]:
    return [sum(values[i:i+period]) / period for i in range(len(values) - period + 1)]


# ── RSI ───────────────────────────────────────────────────────────────────────

def rsi(values: List[float], period: int = 14) -> Optional[float]:
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


# ── MACD ──────────────────────────────────────────────────────────────────────

def macd(values: List[float],
         fast: int = 12, slow: int = 26, signal: int = 9
         ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Returns (macd_line, signal_line, histogram) or (None,None,None)."""
    if len(values) < slow + signal:
        return None, None, None
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    min_len = min(len(ema_fast), len(ema_slow))
    macd_line = [f - s for f, s in zip(ema_fast[-min_len:], ema_slow[-min_len:])]
    sig_line = ema(macd_line, signal)
    if not sig_line:
        return None, None, None
    hist = macd_line[-1] - sig_line[-1]
    return round(macd_line[-1], 6), round(sig_line[-1], 6), round(hist, 6)


# ── Bollinger Bands ────────────────────────────────────────────────────────────

def bollinger(values: List[float], period: int = 20, std_dev: float = 2.0
              ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Returns (upper, mid, lower) or (None,None,None)."""
    if len(values) < period:
        return None, None, None
    window = values[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(variance)
    return round(mid + std_dev * std, 5), round(mid, 5), round(mid - std_dev * std, 5)


# ── ATR ────────────────────────────────────────────────────────────────────────

def atr(candles: list, period: int = 14) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return None
    return round(sum(trs[-period:]) / period, 5)


# ── Support / Resistance ────────────────────────────────────────────────────────

def support_resistance(candles: list, lookback: int = 20) -> Tuple[float, float]:
    recent = candles[-lookback:]
    support    = min(c["low"] for c in recent)
    resistance = max(c["high"] for c in recent)
    return round(support, 5), round(resistance, 5)


# ── Composite technical signal ────────────────────────────────────────────────

def technical_signal(candles: list) -> Dict:
    """
    Combine multiple indicators into a consolidated technical score.
    Returns dict with individual values and an overall bias.
    """
    if len(candles) < 30:
        return {"bias": "HOLD", "score": 0.0, "details": "Not enough candles"}

    closes = _closes(candles)
    score = 0.0
    details = []

    # EMA 20 vs 50 crossover
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    if ema20 and ema50:
        last20, last50 = ema20[-1], ema50[-1]
        if last20 > last50:
            score += 1.5
            details.append(f"EMA20 ({last20:.5f}) > EMA50 ({last50:.5f}) → bullish trend")
        else:
            score -= 1.5
            details.append(f"EMA20 ({last20:.5f}) < EMA50 ({last50:.5f}) → bearish trend")

    # RSI
    rsi_val = rsi(closes)
    if rsi_val is not None:
        if rsi_val < 30:
            score += 2.0
            details.append(f"RSI {rsi_val} — oversold → bullish reversal signal")
        elif rsi_val > 70:
            score -= 2.0
            details.append(f"RSI {rsi_val} — overbought → bearish reversal signal")
        elif rsi_val > 55:
            score += 0.5
            details.append(f"RSI {rsi_val} — bullish momentum")
        elif rsi_val < 45:
            score -= 0.5
            details.append(f"RSI {rsi_val} — bearish momentum")

    # MACD
    m, s, h = macd(closes)
    if h is not None:
        if h > 0 and m > 0:
            score += 1.5
            details.append(f"MACD bullish crossover (hist={h:.6f})")
        elif h < 0 and m < 0:
            score -= 1.5
            details.append(f"MACD bearish crossover (hist={h:.6f})")

    # Bollinger Band squeeze / breakout
    upper, mid, lower = bollinger(closes)
    last_close = closes[-1]
    if upper and lower:
        if last_close > upper:
            score -= 1.0
            details.append(f"Price above upper Bollinger ({upper:.5f}) → potential reversal")
        elif last_close < lower:
            score += 1.0
            details.append(f"Price below lower Bollinger ({lower:.5f}) → potential reversal")

    # Bias
    if score >= 2.0:
        bias = "BUY"
    elif score <= -2.0:
        bias = "SELL"
    else:
        bias = "HOLD"

    return {
        "bias": bias,
        "score": round(score, 2),
        "rsi": rsi_val,
        "macd_hist": h,
        "ema20": ema20[-1] if ema20 else None,
        "ema50": ema50[-1] if ema50 else None,
        "atr": atr(candles),
        "details": " | ".join(details)
    }
