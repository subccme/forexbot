"""
core/price_provider.py  –  Live Forex price fetching
Supports: OANDA REST v3, Alpha Vantage
"""

import requests
import logging
from typing import Optional, Dict
from config.settings import Settings

logger = logging.getLogger("price_provider")

# ─────────────────────────────────────────────────────────────────────────────
# Data class
# ─────────────────────────────────────────────────────────────────────────────

class PriceData:
    def __init__(self, pair: str, bid: float, ask: float, mid: float,
                 spread_pips: float, source: str):
        self.pair = pair
        self.bid = bid
        self.ask = ask
        self.mid = mid
        self.spread_pips = spread_pips
        self.source = source

    def __repr__(self):
        return (f"<PriceData {self.pair} bid={self.bid:.5f} "
                f"ask={self.ask:.5f} spread={self.spread_pips:.1f}p>")


# ─────────────────────────────────────────────────────────────────────────────
# OANDA provider
# ─────────────────────────────────────────────────────────────────────────────

class OandaProvider:
    """
    OANDA REST v3 live/practice price feed.
    Pair format: EUR_USD, GBP_USD, USD_JPY
    """

    def __init__(self, settings: Settings):
        self.api_key = settings.OANDA_API_KEY
        self.account_id = settings.OANDA_ACCOUNT_ID
        self.base_url = settings.OANDA_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def get_price(self, pair: str) -> Optional[PriceData]:
        try:
            url = f"{self.base_url}/accounts/{self.account_id}/pricing"
            r = self.session.get(url, params={"instruments": pair}, timeout=10)
            r.raise_for_status()
            prices = r.json().get("prices", [])
            if not prices:
                return None
            p = prices[0]
            bid = float(p["bids"][0]["price"])
            ask = float(p["asks"][0]["price"])
            mid = (bid + ask) / 2
            # pip value: JPY pairs = 0.01, others = 0.0001
            pip = 0.01 if "JPY" in pair else 0.0001
            spread = (ask - bid) / pip
            return PriceData(pair, bid, ask, mid, spread, "oanda")
        except Exception as e:
            logger.error(f"OANDA price fetch error for {pair}: {e}")
            return None

    def get_account_balance(self) -> Optional[float]:
        try:
            url = f"{self.base_url}/accounts/{self.account_id}/summary"
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            return float(r.json()["account"]["balance"])
        except Exception as e:
            logger.error(f"OANDA balance error: {e}")
            return None

    def get_candles(self, pair: str, granularity: str = "H1",
                    count: int = 50) -> list:
        """Fetch OHLCV candles. granularity: S5,M1,M5,M15,H1,H4,D"""
        try:
            url = f"{self.base_url}/instruments/{pair}/candles"
            r = self.session.get(url, params={
                "granularity": granularity,
                "count": count,
                "price": "M"       # midpoint
            }, timeout=15)
            r.raise_for_status()
            candles = r.json().get("candles", [])
            result = []
            for c in candles:
                if c.get("complete"):
                    m = c["mid"]
                    result.append({
                        "time": c["time"],
                        "open":  float(m["o"]),
                        "high":  float(m["h"]),
                        "low":   float(m["l"]),
                        "close": float(m["c"]),
                        "volume": int(c.get("volume", 0))
                    })
            return result
        except Exception as e:
            logger.error(f"OANDA candles error for {pair}: {e}")
            return []

    def place_order(self, pair: str, side: str, units: int,
                    sl_price: Optional[float] = None,
                    tp_price: Optional[float] = None) -> Optional[dict]:
        """
        side: "buy" | "sell"
        units: positive = buy, negative = sell (OANDA convention)
        """
        if side == "sell":
            units = -abs(units)
        payload = {
            "order": {
                "type": "MARKET",
                "instrument": pair,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT"
            }
        }
        if sl_price:
            payload["order"]["stopLossOnFill"] = {"price": f"{sl_price:.5f}"}
        if tp_price:
            payload["order"]["takeProfitOnFill"] = {"price": f"{tp_price:.5f}"}
        try:
            url = f"{self.base_url}/accounts/{self.account_id}/orders"
            r = self.session.post(url, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"OANDA order error: {e}")
            return None

    def close_all_positions(self) -> bool:
        try:
            url = f"{self.base_url}/accounts/{self.account_id}/positions"
            r = self.session.get(url, timeout=10)
            positions = r.json().get("positions", [])
            for pos in positions:
                pair = pos["instrument"]
                long_units  = int(pos["long"]["units"])
                short_units = int(pos["short"]["units"])
                if long_units != 0 or short_units != 0:
                    close_url = f"{self.base_url}/accounts/{self.account_id}/positions/{pair}/close"
                    body = {}
                    if long_units > 0:
                        body["longUnits"] = "ALL"
                    if short_units < 0:
                        body["shortUnits"] = "ALL"
                    self.session.put(close_url, json=body, timeout=10)
            return True
        except Exception as e:
            logger.error(f"Close all positions error: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Alpha Vantage provider (read-only, no order execution)
# ─────────────────────────────────────────────────────────────────────────────

class AlphaVantageProvider:
    """
    Alpha Vantage free-tier price feed (rate limited to 5 req/min).
    Pair format: EUR/USD → from_symbol=EUR, to_symbol=USD
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, settings: Settings):
        self.api_key = settings.ALPHA_VANTAGE_KEY

    def _av_pair(self, pair: str):
        """'EUR_USD' → ('EUR','USD')"""
        parts = pair.replace("/", "_").split("_")
        return parts[0], parts[1]

    def get_price(self, pair: str) -> Optional[PriceData]:
        from_sym, to_sym = self._av_pair(pair)
        try:
            r = requests.get(self.BASE_URL, params={
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": from_sym,
                "to_currency": to_sym,
                "apikey": self.api_key
            }, timeout=15)
            r.raise_for_status()
            data = r.json().get("Realtime Currency Exchange Rate", {})
            rate = float(data.get("5. Exchange Rate", 0))
            bid  = float(data.get("8. Bid Price", rate * 0.9999))
            ask  = float(data.get("9. Ask Price", rate * 1.0001))
            pip  = 0.01 if "JPY" in pair else 0.0001
            spread = (ask - bid) / pip
            return PriceData(pair, bid, ask, rate, spread, "alphavantage")
        except Exception as e:
            logger.error(f"AlphaVantage price error for {pair}: {e}")
            return None

    def get_candles(self, pair: str, interval: str = "60min",
                    outputsize: str = "compact") -> list:
        from_sym, to_sym = self._av_pair(pair)
        try:
            r = requests.get(self.BASE_URL, params={
                "function": "FX_INTRADAY",
                "from_symbol": from_sym,
                "to_symbol": to_sym,
                "interval": interval,
                "outputsize": outputsize,
                "apikey": self.api_key
            }, timeout=20)
            r.raise_for_status()
            ts_key = f"Time Series FX ({interval})"
            raw = r.json().get(ts_key, {})
            result = []
            for t, vals in sorted(raw.items()):
                result.append({
                    "time": t,
                    "open":  float(vals["1. open"]),
                    "high":  float(vals["2. high"]),
                    "low":   float(vals["3. low"]),
                    "close": float(vals["4. close"]),
                    "volume": 0
                })
            return result
        except Exception as e:
            logger.error(f"AlphaVantage candles error: {e}")
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_price_provider(settings: Settings, broker: str = "oanda"):
    if broker == "oanda":
        return OandaProvider(settings)
    elif broker == "alphavantage":
        return AlphaVantageProvider(settings)
    else:
        logger.warning(f"Unknown broker '{broker}', falling back to AlphaVantage (read-only)")
        return AlphaVantageProvider(settings)
