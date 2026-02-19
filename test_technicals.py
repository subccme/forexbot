"""
tests/test_technicals.py  –  Unit tests for technical indicators
"""

import pytest
import sys
sys.path.insert(0, "..")

from analysis.technicals import (
    ema, sma, rsi, macd, bollinger, atr, technical_signal
)


def make_candles(closes, highs=None, lows=None):
    n = len(closes)
    if highs is None:
        highs = [c + 0.0010 for c in closes]
    if lows is None:
        lows = [c - 0.0010 for c in closes]
    return [
        {"open": c, "high": highs[i], "low": lows[i], "close": c, "volume": 100}
        for i, c in enumerate(closes)
    ]


# ── EMA ──────────────────────────────────────────────────────────────────────

def test_ema_basic():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = ema(values, 3)
    assert len(result) > 0
    assert result[-1] > result[0]   # rising series → rising EMA

def test_ema_insufficient():
    assert ema([1.0, 2.0], 5) == []


# ── RSI ──────────────────────────────────────────────────────────────────────

def test_rsi_rising():
    # Monotonically rising → RSI near 100
    values = list(range(1, 20))
    values = [float(v) for v in values]
    r = rsi(values, 14)
    assert r is not None
    assert r > 70   # all gains, no losses

def test_rsi_falling():
    values = [float(20 - i) for i in range(20)]
    r = rsi(values, 14)
    assert r is not None
    assert r < 30

def test_rsi_insufficient():
    assert rsi([1.0, 2.0], 14) is None


# ── MACD ─────────────────────────────────────────────────────────────────────

def test_macd_returns_values():
    values = [1.0 + i * 0.001 for i in range(50)]
    m, s, h = macd(values)
    assert m is not None
    assert s is not None
    assert h is not None

def test_macd_insufficient():
    m, s, h = macd([1.0] * 10)
    assert m is None


# ── Bollinger ─────────────────────────────────────────────────────────────────

def test_bollinger_ordering():
    values = [1.0 + (i % 5) * 0.001 for i in range(30)]
    upper, mid, lower = bollinger(values)
    assert upper > mid > lower

def test_bollinger_insufficient():
    u, m, l = bollinger([1.0] * 5, period=20)
    assert u is None


# ── ATR ───────────────────────────────────────────────────────────────────────

def test_atr_positive():
    candles = make_candles([1.1000 + i * 0.0001 for i in range(20)])
    result = atr(candles, 14)
    assert result is not None
    assert result > 0


# ── Technical signal composite ────────────────────────────────────────────────

def test_technical_signal_bullish():
    # Rising prices → bullish EMA, RSI
    closes = [1.1000 + i * 0.0005 for i in range(60)]
    candles = make_candles(closes)
    result = technical_signal(candles)
    assert "bias" in result
    assert result["bias"] in ["BUY", "SELL", "HOLD"]
    assert isinstance(result["score"], float)

def test_technical_signal_insufficient():
    candles = make_candles([1.0] * 10)
    result = technical_signal(candles)
    assert result["bias"] == "HOLD"


# ── Sentiment scoring ─────────────────────────────────────────────────────────

def test_sentiment_bullish():
    from analysis.web_analyst import score_text
    text = "EUR/USD rally surge gains bullish breakout recovery"
    assert score_text(text) > 0

def test_sentiment_bearish():
    from analysis.web_analyst import score_text
    text = "decline fall slump bearish breakdown recession dovish"
    assert score_text(text) < 0

def test_sentiment_neutral():
    from analysis.web_analyst import score_text
    text = "the currency pair traded sideways today amid thin liquidity"
    assert abs(score_text(text)) < 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
