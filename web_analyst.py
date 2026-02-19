"""
analysis/web_analyst.py  –  Real-time web-search driven market analysis

Queries SerpAPI / Google CSE to gather:
  • News sentiment  (Reuters, Bloomberg, FXStreet, Investing.com)
  • Economic calendar events
  • Technical pattern commentary
  • Central bank / interest-rate signals

Returns a TradeSignal with direction, confidence, and reasoning.
"""

import re
import time
import logging
import requests
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from config.settings import Settings

logger = logging.getLogger("web_analyst")


# ─────────────────────────────────────────────────────────────────────────────
# Signal output
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TradeSignal:
    pair: str
    direction: str          # "BUY" | "SELL" | "HOLD"
    confidence: float       # 0.0 – 1.0
    reasons: List[str] = field(default_factory=list)
    news_snippets: List[str] = field(default_factory=list)
    raw_score: float = 0.0  # positive = bullish, negative = bearish

    def summary(self) -> str:
        emoji = {"BUY": "📈", "SELL": "📉", "HOLD": "⏸️"}.get(self.direction, "❓")
        lines = [f"{emoji} *{self.pair}* — {self.direction} (confidence: {self.confidence:.0%})"]
        for r in self.reasons[:4]:
            lines.append(f"  • {r}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Keyword sentiment scoring
# ─────────────────────────────────────────────────────────────────────────────

BULLISH_WORDS = [
    "bullish", "rally", "surge", "gains", "uptick", "hawkish",
    "rate hike", "strong", "beat", "optimistic", "recovery",
    "buy", "uptrend", "resistance broken", "breakout", "support holds"
]
BEARISH_WORDS = [
    "bearish", "decline", "drop", "fall", "slump", "dovish",
    "rate cut", "weak", "miss", "pessimistic", "recession",
    "sell", "downtrend", "support broken", "breakdown", "resistance holds",
    "risk-off", "safe haven"
]

def score_text(text: str) -> float:
    """Return sentiment score: positive = bullish, negative = bearish."""
    t = text.lower()
    score = 0.0
    for w in BULLISH_WORDS:
        score += t.count(w) * 1.0
    for w in BEARISH_WORDS:
        score -= t.count(w) * 1.0
    return score


# ─────────────────────────────────────────────────────────────────────────────
# Currency-specific keyword helpers
# ─────────────────────────────────────────────────────────────────────────────

PAIR_KEYWORDS = {
    "EUR_USD": ["EUR/USD", "euro dollar", "ECB", "Federal Reserve", "eurozone", "EURUSD"],
    "GBP_USD": ["GBP/USD", "pound dollar", "Bank of England", "BOE", "sterling", "GBPUSD"],
    "USD_JPY": ["USD/JPY", "dollar yen", "Bank of Japan", "BOJ", "yen", "USDJPY"],
    "AUD_USD": ["AUD/USD", "aussie dollar", "RBA", "Reserve Bank Australia", "AUDUSD"],
    "USD_CAD": ["USD/CAD", "dollar loonie", "Bank of Canada", "BOC", "USDCAD"],
    "USD_CHF": ["USD/CHF", "dollar franc", "SNB", "Swiss National Bank", "USDCHF"],
}

SEARCH_TEMPLATES = [
    "{pair_display} forecast today",
    "{pair_display} technical analysis signal",
    "{currency1} {currency2} market sentiment news",
    "{pair_display} economic calendar impact",
]


# ─────────────────────────────────────────────────────────────────────────────
# Search providers
# ─────────────────────────────────────────────────────────────────────────────

class SerpAPISearcher:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, num: int = 5) -> List[dict]:
        try:
            r = requests.get("https://serpapi.com/search", params={
                "q": query,
                "api_key": self.api_key,
                "num": num,
                "engine": "google",
                "gl": "us",
                "hl": "en"
            }, timeout=15)
            r.raise_for_status()
            results = []
            for item in r.json().get("organic_results", [])[:num]:
                results.append({
                    "title":   item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "source":  item.get("displayed_link", ""),
                    "link":    item.get("link", "")
                })
            return results
        except Exception as e:
            logger.error(f"SerpAPI error: {e}")
            return []


class GoogleCSESearcher:
    def __init__(self, api_key: str, cse_id: str):
        self.api_key = api_key
        self.cse_id = cse_id

    def search(self, query: str, num: int = 5) -> List[dict]:
        try:
            r = requests.get("https://www.googleapis.com/customsearch/v1", params={
                "key": self.api_key,
                "cx":  self.cse_id,
                "q":   query,
                "num": min(num, 10)
            }, timeout=15)
            r.raise_for_status()
            results = []
            for item in r.json().get("items", [])[:num]:
                results.append({
                    "title":   item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "source":  item.get("displayLink", ""),
                    "link":    item.get("link", "")
                })
            return results
        except Exception as e:
            logger.error(f"Google CSE error: {e}")
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Main analyst
# ─────────────────────────────────────────────────────────────────────────────

class WebAnalyst:
    """
    Performs web-search-based analysis for a currency pair.
    Does NOT use any pre-trained ML models — signals are derived
    purely from real-time web search result snippets.
    """

    # Trusted financial sources (for boosting snippet weight)
    TRUSTED_SOURCES = [
        "reuters.com", "bloomberg.com", "investing.com",
        "fxstreet.com", "dailyfx.com", "forexfactory.com",
        "marketwatch.com", "cnbc.com", "ft.com",
        "babypips.com", "tradingeconomics.com"
    ]

    CONFIDENCE_THRESHOLD = 0.35   # minimum confidence to signal BUY/SELL

    def __init__(self, settings: Settings):
        self.settings = settings
        if settings.SERP_API_KEY:
            self.searcher = SerpAPISearcher(settings.SERP_API_KEY)
            logger.info("Using SerpAPI for web search")
        elif settings.GOOGLE_CSE_KEY:
            self.searcher = GoogleCSESearcher(settings.GOOGLE_CSE_KEY, settings.GOOGLE_CSE_ID)
            logger.info("Using Google CSE for web search")
        else:
            raise ValueError("No web search API configured")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _pair_display(self, pair: str) -> str:
        return pair.replace("_", "/")

    def _build_queries(self, pair: str) -> List[str]:
        kw  = PAIR_KEYWORDS.get(pair, [pair.replace("_", "/")])
        c1, c2 = pair.split("_")
        pd = self._pair_display(pair)
        queries = []
        for tpl in SEARCH_TEMPLATES:
            queries.append(tpl.format(
                pair_display=pd,
                currency1=c1,
                currency2=c2
            ))
        # Economic indicators
        queries.append(f"{c1} economic data release today")
        queries.append(f"{c2} central bank statement news")
        return queries[:5]   # cap at 5 queries per cycle to save credits

    def _source_weight(self, source: str) -> float:
        for ts in self.TRUSTED_SOURCES:
            if ts in source.lower():
                return 1.5
        return 1.0

    # ── Core analysis ────────────────────────────────────────────────────────

    def analyse(self, pair: str) -> TradeSignal:
        logger.info(f"🔍 Web analysis for {pair}...")
        queries = self._build_queries(pair)
        total_score = 0.0
        total_weight = 0.0
        all_snippets = []
        reasons = []

        for q in queries:
            results = self.searcher.search(q, num=5)
            time.sleep(0.5)   # polite delay

            for res in results:
                text = f"{res['title']} {res['snippet']}"
                raw  = score_text(text)
                w    = self._source_weight(res["source"])
                total_score  += raw * w
                total_weight += w

                if res["snippet"]:
                    snippet = f"[{res['source']}] {res['snippet'][:120]}"
                    all_snippets.append(snippet)

                # Collect human-readable reason when strong signal
                if abs(raw) >= 2:
                    direction_word = "bullish" if raw > 0 else "bearish"
                    reasons.append(f"{direction_word.capitalize()} signal from {res['source']}: \"{res['title'][:80]}\"")

            logger.debug(f"Query '{q[:60]}' → {len(results)} results")

        # Normalise
        if total_weight > 0:
            normalised = total_score / total_weight
        else:
            normalised = 0.0

        # Map score → direction + confidence
        # Confidence saturates at ±10 score range
        confidence = min(abs(normalised) / 10.0, 1.0)
        if normalised > 0 and confidence >= self.CONFIDENCE_THRESHOLD:
            direction = "BUY"
        elif normalised < 0 and confidence >= self.CONFIDENCE_THRESHOLD:
            direction = "SELL"
        else:
            direction = "HOLD"

        if not reasons:
            reasons.append(f"Aggregate web sentiment score: {normalised:+.2f}")

        logger.info(f"✅ {pair}: {direction} (confidence={confidence:.1%}, score={normalised:+.2f})")

        return TradeSignal(
            pair=pair,
            direction=direction,
            confidence=confidence,
            reasons=reasons[:5],
            news_snippets=all_snippets[:6],
            raw_score=normalised
        )

    def analyse_all(self, pairs: List[str]) -> List[TradeSignal]:
        signals = []
        for pair in pairs:
            try:
                sig = self.analyse(pair)
                signals.append(sig)
            except Exception as e:
                logger.error(f"Analysis failed for {pair}: {e}")
        return signals
