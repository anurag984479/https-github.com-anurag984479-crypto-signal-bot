# PEPPERSTONE ADAPTIVE BOT v15.0 — LIVE MARKET UPGRADE

```python
import time
import logging
import requests
import ccxt
import pandas as pd
import ta
import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

# ═══════════════════════════════════════════════════════════════
# LIVE MARKET CONFIGURATION
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v15.0")

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise ValueError("Missing Telegram credentials in environment variables")

EXCHANGE = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "spot"}
})

# ═══════════════════════════════════════════════════════════════
# MARKET SETTINGS
# ═══════════════════════════════════════════════════════════════
MARKETS = {
    "XAU/USD": {
        "yf": "GC=F",
        "sessions": [7, 20],
        "decimals": 2,
        "min_sl": 25.0,
        "spread": 1.5,
    },
    "BTC/USD": {
        "crypto": "BTC/USDT",
        "sessions": [0, 23],
        "decimals": 2,
        "min_sl": 500.0,
        "spread": 50,
    },
    "GBP/USD": {
        "yf": "GBPUSD=X",
        "sessions": [7, 20],
        "decimals": 5,
        "min_sl": 0.0030,
        "spread": 0.0003,
    },
    "ETH/USD": {
        "crypto": "ETH/USDT",
        "sessions": [0, 23],
        "decimals": 2,
        "min_sl": 25.0,
        "spread": 5,
    },
    "US500": {
        "yf": "^GSPC",
        "sessions": [13, 21],
        "decimals": 2,
        "min_sl": 20.0,
        "spread": 1.0,
    },
}

SYMBOLS = list(MARKETS.keys())

# ═══════════════════════════════════════════════════════════════
# STRATEGY PARAMETERS
# ═══════════════════════════════════════════════════════════════
VOL_MULT = 1.2
SIGNAL_COOLDOWN = 1800
CONFIRM_THRESHOLD = 3
ADX_THRESHOLD = 22
HTF_REFRESH = 3600

_signal_sent = {s: 0 for s in SYMBOLS}
_htf_cache = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}
_active_trades = {}

# ═══════════════════════════════════════════════════════════════
# TELEGRAM ALERTS
# ═══════════════════════════════════════════════════════════════
def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ═══════════════════════════════════════════════════════════════
# SESSION FILTER
# ═══════════════════════════════════════════════════════════════
def session_active(symbol_key):
    start, end = MARKETS[symbol_key]["sessions"]
    hour = datetime.now(timezone.utc).hour
    return start <= hour <= end

# ═══════════════════════════════════════════════════════════════
# YAHOO FETCH
# ═══════════════════════════════════════════════════════════════
def fetch_yf(ticker, period="5d", interval="15m"):
    try:
        raw = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True
        )

        if raw.empty:
            return None

        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        raw.columns = [str(c).lower() for c in raw.columns]
        return raw[["open", "high", "low", "close", "volume"]].reset_index(drop=True)

    except Exception as e:
        log.error(f"Yahoo fetch error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
# CRYPTO FETCH
# ═══════════════════════════════════════════════════════════════
def fetch_crypto(symbol, timeframe="15m", limit=300):
    try:
        ohlcv = EXCHANGE.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        return df[["open", "high", "low", "close", "volume"]]

    except Exception as e:
        log.error(f"Crypto fetch error {symbol}: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
# UNIVERSAL FETCH
# ═══════════════════════════════════════════════════════════════
def fetch_data(symbol_key):
    config = MARKETS[symbol_key]

    if "crypto" in config:
        return fetch_crypto(config["crypto"])
    else:
        return fetch_yf(config["yf"])

# ═══════════════════════════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════════════════════════
def add_indicators(df):
    cl = pd.to_numeric(df["close"])
    hi = pd.to_numeric(df["high"])
    lo = pd.to_numeric(df["low"])
    vol = pd.to_numeric(df["volume"])

    df["rsi"] = ta.momentum.RSIIndicator(cl, 14).rsi()
    df["ema9"] = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(cl, 50).ema_indicator()
    df["atr"] = ta.volatility.AverageTrueRange(hi, lo, cl, 14).average_true_range()
    df["adx"] = ta.trend.ADXIndicator(hi, lo, cl, 14).adx()
    df["volma"] = vol.rolling(20).mean()

    return df

# ═══════════════════════════════════════════════════════════════
# HIGHER TIMEFRAME TREND
# ═══════════════════════════════════════════════════════════════
def get_htf_trend(symbol_key):
    now = time.time()

    if now - _htf_cache[symbol_key]["ts"] < HTF_REFRESH:
        return _htf_cache[symbol_key]["trend"]

    config = MARKETS[symbol_key]

    if "crypto" in config:
        df = fetch_crypto(config["crypto"], timeframe="1h")
    else:
        df = fetch_yf(config["yf"], period="1mo", interval="1h")

    if df is None or len(df) < 50:
        return "NEUTRAL"

    df = add_indicators(df)
    last = df.iloc[-2]

    if last["ema21"] > last["ema50"]:
        trend = "BULL"
    elif last["ema21"] < last["ema50"]:
        trend = "BEAR"
    else:
        trend = "NEUTRAL"

    _htf_cache[symbol_key] = {"trend": trend, "ts": now}
    return trend

# ═══════════════════════════════════════════════════════════════
# SIGNAL CONDITIONS
# ═══════════════════════════════════════════════════════════════
def check_conditions(df, trend):
    last = df.iloc[-2]  # closed candle only

    atr_avg = df["atr"].rolling(50).mean().iloc[-2]

    if last["atr"] > atr_avg:
        rsi_ob = 70
        rsi_os = 30
    else:
        rsi_ob = 65
        rsi_os = 35

    rsi = float(last["rsi"])
    ema9 = float(last["ema9"])
    ema21 = float(last["ema21"])
    ema50 = float(last["ema50"])
    close = float(last["close"])
    op = float(last["open"])
    hi = float(last["high"])
    lo = float(last["low"])
    vol = float(last["volume"])
    volma = float(last["volma"])
    atr = float(last["atr"])
    adx = float(last["adx"])

    body = abs(close - op)
    rng = max(hi - lo, 0.0001)
    body_pct = body / rng
    vol_ok = vol > volma * VOL_MULT if volma > 0 else False

    buy_score = sum([
        rsi < rsi_os,
        ema9 > ema21,
        vol_ok,
        close > op and body_pct > 0.5,
        close > ema50,
    ])

    sell_score = sum([
        rsi > rsi_ob,
        ema9 < ema21,
        vol_ok,
        close < op and body_pct > 0.5,
        close < ema50,
    ])

    if trend == "BULL":
        buy_score += 1
        sell_score = 0
    elif trend == "BEAR":
        sell_score += 1
        buy_score = 0

    return buy_score, sell_score, rsi, close, atr, adx

# ═══════════════════════════════════════════════════════════════
# SL / TP
# ═══════════════════════════════════════════════════════════════
def calc_levels(price, direction, atr, symbol_key, adx):
    min_sl = MARKETS[symbol_key]["min_sl"]
    sl_dist = max(atr * 2, min_sl)

    if adx > 35:
        rr = 4
    elif adx < 25:
        rr = 2
    else:
        rr = 3

    if direction == "BUY":
        sl = price - sl_dist
        tp = price + sl_dist * rr
    else:
        sl = price + sl_dist
        tp = price - sl_dist * rr

    decimals = MARKETS[symbol_key]["decimals"]

    return round(sl, decimals), round(tp, decimals), round(sl_dist, decimals), rr

# ═══════════════════════════════════════════════════════════════
# BREAK-EVEN STOP MANAGEMENT
# ═══════════════════════════════════════════════════════════════
def break_even_trigger(entry, current_price, direction, sl_dist):
    if direction == "BUY":
        return current_price >= entry + sl_dist
    elif direction == "SELL":
        return current_price <= entry - sl_dist
    return False

# ═══════════════════════════════════════════════════════════════
# PROCESS MARKET
# ═══════════════════════════════════════════════════════════════
def process_symbol(symbol_key):
    if not session_active(symbol_key):
        return

    df = fetch_data(symbol_key)
    if df is None or len(df) < 100:
        return

    df = add_indicators(df)
    trend = get_htf_trend(symbol_key)
    buy_score, sell_score, rsi, price, atr, adx = check_conditions(df, trend)

    if adx < ADX_THRESHOLD:
        return

    now = time.time()

    # Manage existing trade for break-even alerts only
    if symbol_key in _active_trades:
        trade = _active_trades[symbol_key]

        if not trade["be_sent"]:
            if break_even_trigger(
                trade["entry"],
                price,
                trade["direction"],
                trade["sl_dist"]
            ):
                send_telegram(
                    f"⚠️ BREAK-EVEN ALERT {symbol_key}
"
                    f"Trade Type: {trade['direction']}
"
                    f"Entry: {trade['entry']}
"
                    f"Current Price: {price}
"
                    f"Action: Close manually or secure profit now."
                )
                trade["be_sent"] = True

        # Silent cleanup when TP reached
        if trade["direction"] == "BUY" and price >= trade["tp"]:
            del _active_trades[symbol_key]
            return
        elif trade["direction"] == "SELL" and price <= trade["tp"]:
            del _active_trades[symbol_key]
            return

    if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
        return

    # BUY SIGNAL
    if buy_score >= CONFIRM_THRESHOLD:
        sl, tp, sl_dist, rr = calc_levels(price, "BUY", atr, symbol_key, adx)
        send_telegram(
            f"🚀 BUY SIGNAL {symbol_key}
"
            f"Entry: {price}
"
            f"SL: {sl}
"
            f"TP: {tp}
"
            f"RSI: {rsi:.1f}
"
            f"ADX: {adx:.1f}
"
            f"Trend: {trend}
"
            f"RR: 1:{rr}"
        )

        _active_trades[symbol_key] = {
            "direction": "BUY",
            "entry": price,
            "sl": sl,
            "tp": tp,
            "sl_dist": sl_dist,
            "be_sent": False,
        }
        _signal_sent[symbol_key] = now

    # SELL SIGNAL
    elif sell_score >= CONFIRM_THRESHOLD:
        sl, tp, sl_dist, rr = calc_levels(price, "SELL", atr, symbol_key, adx)
        send_telegram(
            f"🔻 SELL SIGNAL {symbol_key}
"
            f"Entry: {price}
"
            f"SL: {sl}
"
            f"TP: {tp}
"
            f"RSI: {rsi:.1f}
"
            f"ADX: {adx:.1f}
"
            f"Trend: {trend}
"
            f"RR: 1:{rr}"
        )

        _active_trades[symbol_key] = {
            "direction": "SELL",
            "entry": price,
            "sl": sl,
            "tp": tp,
            "sl_dist": sl_dist,
            "be_sent": False,
        }
        _signal_sent[symbol_key] = now

# ═══════════════════════════════════════════════════════════════
# MAIN BOT LOOP
# ═══════════════════════════════════════════════════════════════
def main():
    log.info("🚀 LIVE MARKET BOT v15 STARTED")

    while True:
        try:
            with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
                futures = [executor.submit(process_symbol, s) for s in SYMBOLS]

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        log.error(f"Thread error: {e}")

            time.sleep(60)

        except KeyboardInterrupt:
            log.info("Bot stopped")
            break

        except Exception as e:
            log.error(f"Main loop error: {e}")
            time.sleep(30)

# ═══════════════════════════════════════════════════════════════
# START
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
```

## Next recommended upgrades

* MT5/Pepperstone direct broker API
* ForexFactory news filter
* Websocket live feeds
* Trade execution module
* Position sizing by equity %
* Trailing stop manager
* Database journaling
* VPS deployment

    
