# 🤖 ForexBot — Automated Forex Trading via Telegram

A production-ready Telegram bot that monitors Forex markets 24/7, performs **real-time web-search-based analysis** (no pre-trained models), and executes trades automatically on your OANDA or Alpha Vantage account.

---

## 📐 Architecture

```
ForexBot/
├── main.py                    ← Entry point, wires everything together
├── config/
│   ├── settings.py            ← Env vars, global config
│   ├── user_db.py             ← JSON user settings store
│   └── trade_log.py           ← Append-only trade journal
├── core/
│   ├── bot_handlers.py        ← All /command handlers
│   ├── price_provider.py      ← OANDA + Alpha Vantage live prices & orders
│   └── scheduler.py           ← Async background analysis loop
├── analysis/
│   ├── web_analyst.py         ← SerpAPI / Google CSE → sentiment scoring
│   └── technicals.py          ← EMA, RSI, MACD, Bollinger, ATR (pure math)
├── trading/
│   └── executor.py            ← Combined signal → position sizing → order
└── utils/
    ├── formatter.py            ← Telegram message templates
    ├── security.py             ← Fernet AES encryption for API keys
    └── logger.py               ← Structured logging to console + file
```

### Analysis Pipeline (per cycle, per pair)

```
Web Search (5 queries)
    ↓ SerpAPI / Google CSE
    ↓ Sentiment scoring (bullish/bearish keyword weights)
    ↓ Source trust weighting (Reuters, Bloomberg > generic sites)
    ↓ TradeSignal: direction + confidence

OANDA Candle Data (60 H1 candles)
    ↓ EMA 20/50 crossover
    ↓ RSI (oversold/overbought)
    ↓ MACD histogram
    ↓ Bollinger Band breakout
    ↓ ATR for dynamic SL/TP
    ↓ TechnicalSignal: bias + score

Combined Signal
    ↓ Agreement → high confidence
    ↓ Disagreement → hold
    ↓ Confidence ≥ 45% → execute
    ↓ Drawdown check
    ↓ Position sizing (risk-based)
    ↓ OANDA order submission
    ↓ Telegram alert to user
```

---

## 🚀 Setup

### 1. Prerequisites

```bash
Python 3.10+
pip install -r requirements.txt
```

### 2. Create your Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow prompts
3. Copy your **Bot Token**

### 3. Get API keys

| Service | Purpose | URL |
|---------|---------|-----|
| OANDA | Live prices + order execution | https://www.oanda.com/register/ |
| Alpha Vantage | Alternative price feed (free) | https://www.alphavantage.co/support/#api-key |
| SerpAPI | Web search for analysis | https://serpapi.com |
| Google CSE | Alternative web search | https://programmablesearchengine.google.com |

> **Recommended:** Use OANDA practice account first (`OANDA_BASE_URL=https://api-fxpractice.oanda.com/v3`)

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your real API keys
```

### 5. Run

```bash
python main.py
```

---

## 📱 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot |
| `/connect oanda YOUR_API_KEY YOUR_ACCOUNT_ID` | Link your broker |
| `/settings` | Open interactive settings panel |
| `/settings risk 1.5` | Set risk to 1.5% per trade |
| `/settings sl 30` | Stop-loss: 30 pips |
| `/settings tp 60` | Take-profit: 60 pips |
| `/settings pairs EUR_USD,GBP_USD,USD_JPY` | Set currency pairs |
| `/settings drawdown 10` | Max 10% drawdown before auto-halt |
| `/settings interval 10` | Scan every 10 minutes |
| `/resume` | Start automated trading |
| `/pause` | Pause (keeps open positions) |
| `/stop` | Stop trading completely |
| `/status` | View connection & trading status |
| `/balance` | Fetch live account balance |
| `/trades` | Show last 10 executed trades |

---

## 🔍 Web Search Query Templates

The analyst builds these queries dynamically for each pair:

```
"EUR/USD forecast today"
"EUR/USD technical analysis signal"
"EUR USD market sentiment news"
"EUR/USD economic calendar impact"
"EUR economic data release today"
"USD central bank statement news"
```

Results are pulled from financial sources like:
- **reuters.com** (1.5× trust weight)
- **bloomberg.com** (1.5× trust weight)
- **investing.com** (1.5× trust weight)
- **fxstreet.com** (1.5× trust weight)
- **dailyfx.com** (1.5× trust weight)
- **forexfactory.com** (1.5× trust weight)
- Generic sources (1.0× weight)

Sentiment is scored by keyword matching:
- **Bullish words:** rally, surge, hawkish, rate hike, breakout, recovery…
- **Bearish words:** decline, dovish, rate cut, breakdown, risk-off, recession…

---

## 🛡️ Safety Features

| Feature | Details |
|---------|---------|
| **Max drawdown halt** | Auto-stops trading if account drops by configured % |
| **Confidence threshold** | Only trades when combined score ≥ 45% |
| **API key encryption** | Fernet AES-128 at rest in `users.json` |
| **Message deletion** | `/connect` message auto-deleted from chat after parsing keys |
| **Graceful error handling** | All API calls wrapped in try/catch with logging |
| **Trade logging** | Every order logged to `data/trades.json` + Telegram alert |
| **No positions auto-close** | `/stop` halts new trades; existing positions stay open (intentional) |

---

## 🔧 Running as a Service (Linux)

```ini
# /etc/systemd/system/forexbot.service
[Unit]
Description=ForexBot Telegram Trading Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/forex_bot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10
EnvironmentFile=/path/to/forex_bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable forexbot
sudo systemctl start forexbot
sudo journalctl -u forexbot -f
```

---

## ⚠️ Risk Disclaimer

> **Forex trading involves substantial risk of loss.** This bot is provided for educational and research purposes. Past performance of any analysis method does not guarantee future results. Always test on a practice account first. Never risk money you cannot afford to lose. The authors are not responsible for any trading losses.

---

## 📈 Extending the Bot

### Add a new broker

1. Create a class in `core/price_provider.py` with `get_price()` and `place_order()` methods
2. Register it in the `create_price_provider()` factory
3. Users connect with `/connect yourbroker api_key account_id`

### Add a new analysis source

Edit `analysis/web_analyst.py`:
- Add queries to `SEARCH_TEMPLATES`
- Add trusted domain to `TRUSTED_SOURCES`
- Adjust `BULLISH_WORDS` / `BEARISH_WORDS`

### Add MetaTrader 4/5 support

Use the [MetaAPI SDK](https://metaapi.cloud) which wraps MT4/5 in a REST API:
```bash
pip install metaapi-cloud-sdk
```
Create `OandaProvider`-compatible wrapper using `MetaApi` and `MetaTrader` classes.
