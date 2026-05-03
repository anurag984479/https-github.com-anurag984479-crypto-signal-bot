import time
import logging
import requests
import ccxt
import pandas as pd
import ta
import os
from datetime import datetime, timezone

# 1. LOGGING SETUP
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("Combined_Scanner")

# 2. CONFIGURATION
TOKEN   = os.getenv("TOKEN", "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

SYMBOLS       = ["BTC/USD", "XAU/USD"]
TIMEFRAME     = "15m"
TIMEFRAME_HTF = "1h"
CANDLE_LIMIT  = 300

# Indicators
RSI_OVERSOLD   = 35
RSI_OVERBOUGHT = 65
STOP_PCT       = 0.005
RR_RATIO       = 2

# Zone Sniper settings
ZONE_LOOKBACK     = 20
ZONE_THRESHOLD    = 0.0015
VOLUME_MULTIPLIER = 1.3
VOLUME_MA_PERIOD  = 20

# Session filter (UTC)
SESSIONS = [
    {"name": "London",   "start": 7,  "end": 12},
    {"name": "New York", "start": 12, "end": 17},
    {"name": "Overlap",  "start": 12, "end": 16},
]

# News blackout — update weekly with NFP, CPI, Fed dates
NEWS_BLACKOUT_MINUTES = 30
HIGH_IMPACT_NEWS = [
    # "2026-05-09 12:30",  # NFP example
]

CHART_LINKS = {
    "BTC/USD": "https://www.tradingview.com/chart/?symbol=COINBASE%3ABTCUSD&interval=15",
    "XAU/USD": "https://www.tradingview.com/chart/?symbol=TVC%3AGOLD&interval=15",
}

# ─────────────────────────────────────────────
# 3. TELEGRAM
# ─────────────────────────────────────────────
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
        log.info("✅ Signal sent to Telegram.")
    except Exception as e:
        log.error(f"❌ Telegram error: {e}")

# ─────────────────────────────────────────────
# 4. SESSION & NEWS FILTERS
# ─────────────────────────────────────────────
def is_valid_session():
    now_hour = datetime.now(timezone.utc).hour
    for s in SESSIONS:
        if s["start"] <= now_hour < s["end"]:
            return True, s["name"]
    return False, "Asian (avoid)"

def is_near_news():
    now = datetime.now(timezone.utc)
    for news_str in HIGH_IMPACT_NEWS:
        try:
            news_dt = datetime.strptime(
                news_str, "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
            diff = abs((now - news_dt).total_seconds() / 60)
            if diff <= NEWS_BLACKOUT_MINUTES:
                log.info(f"📰 News blackout: {news_str} is {diff:.0f}min away")
                return True
        except Exception:
            pass
    return False

# ─────────────────────────────────────────────
# 5. DATA FETCH
# ─────────────────────────────────────────────
def fetch_ohlcv_df(exchange_obj, symbol, timeframe, limit):
    ohlcv = exchange_obj.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(
        ohlcv, columns=["time","open","high","low","close","volume"]
    )
    df["close"]  = pd.to_numeric(df["close"])
    df["EMA50"]  = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    df["EMA200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
    df["RSI"]    = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["vol_ma"] = df["volume"].rolling(VOLUME_MA_PERIOD).mean()
    return df

def fetch_yfinance_df(ticker, period, interval):
    """Shared yfinance fetcher with MultiIndex fix."""
    import yfinance as yf
    raw = yf.download(ticker, period=period, interval=interval, progress=False)
    if raw.empty:
        raise ValueError(f"Empty yfinance response for {ticker}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw[["Open","High","Low","Close","Volume"]].copy()
    df.columns = ["open","high","low","close","volume"]
    df["close"]  = pd.to_numeric(df["close"])
    df["EMA50"]  = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    df["EMA200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
    df["RSI"]    = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["vol_ma"] = df["volume"].rolling(VOLUME_MA_PERIOD).mean()
    return df

# ── BTC ──────────────────────────────────────
def get_btc_data():
    """BTC 15m via Coinbase."""
    try:
        exchange = ccxt.coinbase()
        df = fetch_ohlcv_df(exchange, "BTC/USD", TIMEFRAME, CANDLE_LIMIT)
        return df, exchange
    except Exception as e:
        log.error(f"⚠️ BTC Coinbase error: {e}")

    # Fallback: yfinance BTC
    try:
        df = fetch_yfinance_df("BTC-USD", "5d", "15m")
        log.info("BTC fetched from yfinance BTC-USD")
        return df, None
    except Exception as e:
        log.error(f"⚠️ BTC yfinance error: {e}")
    return None, None

def get_btc_htf(exchange_obj):
    """BTC 1h trend."""
    try:
        if exchange_obj:
            df = fetch_ohlcv_df(exchange_obj, "BTC/USD", TIMEFRAME_HTF, 250)
        else:
            df = fetch_yfinance_df("BTC-USD", "30d", "1h")
        row = df.iloc[-1]
        if row["EMA50"] > row["EMA200"]: return "BULL"
        if row["EMA50"] < row["EMA200"]: return "BEAR"
    except Exception as e:
        log.warning(f"BTC HTF error: {e}")
    return "NEUTRAL"

# ── GOLD ─────────────────────────────────────
def get_gold_data():
    """
    Gold 15m — fallback chain:
    Kraken XAU/USD → Kraken XAUUSD → Bitfinex →
    yfinance XAUUSD=X → yfinance GC=F
    """
    for source, sym in [
        ("kraken",  "XAU/USD"),
        ("kraken",  "XAUUSD"),
        ("bitfinex","XAU/USD"),
    ]:
        try:
            exchange = getattr(ccxt, source)()
            df = fetch_ohlcv_df(exchange, sym, TIMEFRAME, CANDLE_LIMIT)
            log.info(f"Gold 15m fetched from {source} ({sym})")
            return df, exchange
        except Exception as e:
            log.warning(f"{source} {sym} failed: {e}")

    # yfinance XAUUSD=X  ← correct spot price
    for ticker in ["XAUUSD=X", "GC=F"]:
        try:
            df = fetch_yfinance_df(ticker, "5d", "15m")
            log.info(f"Gold 15m fetched from yfinance ({ticker})")
            return df, None
        except Exception as e:
            log.warning(f"yfinance {ticker} failed: {e}")

    log.error("⚠️ All Gold 15m sources failed")
    return None, None

def get_gold_htf(exchange_obj):
    """Gold 1h trend."""
    try:
        if exchange_obj:
            df = fetch_ohlcv_df(exchange_obj, "XAU/USD", TIMEFRAME_HTF, 250)
        else:
            df = fetch_yfinance_df("XAUUSD=X", "30d", "1h")
        row = df.iloc[-1]
        if row["EMA50"] > row["EMA200"]: return "BULL"
        if row["EMA50"] < row["EMA200"]: return "BEAR"
    except Exception as e:
        log.warning(f"Gold HTF error: {e}")
    return "NEUTRAL"

# ─────────────────────────────────────────────
# 6. ZONE DETECTION
# ─────────────────────────────────────────────
def detect_zones(df):
    recent = df.tail(ZONE_LOOKBACK).copy()
    zones  = {"demand": [], "supply": []}
    for i in range(2, len(recent) - 1):
        prev = recent.iloc[i - 1]
        curr = recent.iloc[i]
        size = abs(curr["high"] - curr["low"])
        if size == 0:
            continue
        if (prev["close"] < prev["open"] and
                curr["close"] > curr["open"] and
                (curr["close"] - curr["open"]) / size > 0.6):
            zones["demand"].append(curr["low"])
        if (prev["close"] > prev["open"] and
                curr["close"] < curr["open"] and
                (curr["open"] - curr["close"]) / size > 0.6):
            zones["supply"].append(curr["high"])
    return zones

def price_near_zone(price, levels):
    return any(abs(price - lvl) / lvl <= ZONE_THRESHOLD for lvl in levels)

# ─────────────────────────────────────────────
# 7. SIGNAL ENGINE
# ─────────────────────────────────────────────
def evaluate_signal(df, htf_trend, price, rsi, ema50, ema200, vol, vol_ma):
    is_bullish = ema50 > ema200
    zones      = detect_zones(df)
    volume_ok  = vol >= vol_ma * VOLUME_MULTIPLIER

    buy_checks = {
        "EMA bullish (15m)": is_bullish,
        "HTF bullish (1h)":  htf_trend in ("BULL", "NEUTRAL"),
        "RSI oversold":      rsi < RSI_OVERSOLD,
        "In demand zone":    price_near_zone(price, zones["demand"]),
        "Volume confirmed":  volume_ok,
    }
    sell_checks = {
        "EMA bearish (15m)": not is_bullish,
        "HTF bearish (1h)":  htf_trend in ("BEAR", "NEUTRAL"),
        "RSI overbought":    rsi > RSI_OVERBOUGHT,
        "In supply zone":    price_near_zone(price, zones["supply"]),
        "Volume confirmed":  volume_ok,
    }

    if all(buy_checks.values()):
        return "LONG / BUY",   [k for k,v in buy_checks.items()  if v], buy_checks, sell_checks
    if all(sell_checks.values()):
        return "SHORT / SELL", [k for k,v in sell_checks.items() if v], buy_checks, sell_checks

    return "NONE", [], buy_checks, sell_checks

# ─────────────────────────────────────────────
# 8. SCANNER
# ─────────────────────────────────────────────
def scan_symbol(symbol):
    # Session filter
    in_session, session_name = is_valid_session()
    if not in_session:
        log.info(f"🌙 {symbol}: Outside session ({session_name}) — skipping")
        return

    # News filter
    if is_near_news():
        log.info(f"📰 {symbol}: News blackout — skipping")
        return

    # Fetch data
    if symbol == "BTC/USD":
        df, exchange_obj = get_btc_data()
        htf_trend = get_btc_htf(exchange_obj)
        header    = "🚨 *COINBASE BTC SIGNAL* 🚨"
    else:
        df, exchange_obj = get_gold_data()
        htf_trend = get_gold_htf(exchange_obj)
        header    = "🚨 *GOLD ZONE SNIPER SIGNAL* 🚨"

    if df is None:
        return

    row    = df.iloc[-1]
    price  = row["close"]
    rsi    = row["RSI"]
    ema50  = row["EMA50"]
    ema200 = row["EMA200"]
    vol    = row["volume"]
    vol_ma = row["vol_ma"]

    if pd.isna(rsi) or pd.isna(ema50) or pd.isna(ema200) or pd.isna(vol_ma):
        log.warning(f"{symbol}: Indicators not ready yet")
        return

    # Evaluate
    signal, conditions_met, buy_checks, sell_checks = evaluate_signal(
        df, htf_trend, price, rsi, ema50, ema200, vol, vol_ma
    )

    if signal != "NONE":
        is_bullish = ema50 > ema200
        if signal == "LONG / BUY":
            sl = price * (1 - STOP_PCT)
            tp = price + (price - sl) * RR_RATIO
        else:
            sl = price * (1 + STOP_PCT)
            tp = price - (sl - price) * RR_RATIO

        passed_str = "\n".join([f"  ✅ {c}" for c in conditions_met])
        msg = (
            f"{header}\n\n"
            f"🔥 *Action:* {signal}\n"
            f"💹 *Price:* ${price:,.2f}\n"
            f"📍 *Entry:* {price:,.2f}\n"
            f"🛑 *Stop Loss:* {sl:,.2f}\n"
            f"🎯 *Take Profit:* {tp:,.2f}\n"
            f"⚖️ *R:R:* 1:{RR_RATIO}\n\n"
            f"📊 *Trend (15m):* {'Bullish 📈' if is_bullish else 'Bearish 📉'}\n"
            f"📈 *RSI:* {rsi:.1f}\n"
            f"🌍 *HTF (1h):* {htf_trend}\n"
            f"⏰ *Session:* {session_name}\n\n"
            f"*All 5 conditions met:*\n{passed_str}\n\n"
            f"🔗 [Open Chart]({CHART_LINKS[symbol]})"
        )
        send_telegram_alert(msg)
        log.info(f"✅ {symbol} Signal: {signal} — 10min cooldown")
        time.sleep(600)

    else:
        buy_score  = sum(v for v in buy_checks.values())
        sell_score = sum(v for v in sell_checks.values())
        best_score = max(buy_score, sell_score)
        is_bullish = ema50 > ema200
        log.info(
            f"Heartbeat {symbol} | Price: {price:.2f} | RSI: {rsi:.2f} | "
            f"HTF: {htf_trend} | Session: {session_name} | "
            f"Score: {best_score}/5 | Trend: {'Bullish' if is_bullish else 'Bearish'}"
        )

# ─────────────────────────────────────────────
# 9. MAIN LOOP
# ─────────────────────────────────────────────
def main():
    log.info("🚀 ZONE SNIPER v2.0 — BTC + GOLD | 15m + 1h HTF | Target: 72-75%")
    log.info("📊 Filters: Session + News + HTF + Zone + Volume — ALL 5 required")
    while True:
        try:
            for symbol in SYMBOLS:
                scan_symbol(symbol)
            time.sleep(30)
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()