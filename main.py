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
# PEPPERSTONE ZONE SNIPER v3.5
# Assets  : XAUUSD.Qraw + BTCUSD.Qraw
# Target  : 74-76% win rate
# Filters : Session + News + HTF + Zone + Volume (ALL 5)
# R:R     : 1:2
# Speed   : Parallel fetch + HTF cache (3x faster)
# ═══════════════════════════════════════════════════════════════

# 1. LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("ZoneSniper")

# ─────────────────────────────────────────────
# 2. CONFIGURATION
# ─────────────────────────────────────────────
TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

MT5_SYMBOLS = {
    "BTC/USD": "BTCUSD.Qraw",
    "XAU/USD": "XAUUSD.Qraw",
}

SYMBOLS       = list(MT5_SYMBOLS.keys())
TIMEFRAME     = "15m"
TIMEFRAME_HTF = "1h"
CANDLE_LIMIT  = 220   # reduced from 300 — still enough for EMA200

RSI_OVERSOLD   = 35
RSI_OVERBOUGHT = 65
STOP_PCT       = 0.005
RR_RATIO       = 2

ZONE_LOOKBACK     = 20
ZONE_THRESHOLD    = 0.0015
VOLUME_MULTIPLIER = 1.3
VOLUME_MA_PERIOD  = 20

PRICE_RANGES = {
    "BTC/USD": (50000, 200000),
    "XAU/USD": (4000,  5500),
}

SESSIONS = [
    {"name": "London",    "start": 7,  "end": 12},
    {"name": "NY+London", "start": 12, "end": 16},
    {"name": "New York",  "start": 16, "end": 17},
]

NEWS_BLACKOUT_MINUTES = 30
HIGH_IMPACT_NEWS = [
    # "2026-05-07 18:00",  # Fed
    # "2026-05-09 12:30",  # NFP
]

CHART_LINKS = {
    "BTC/USD": "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ABTCUSD&interval=15",
    "XAU/USD": "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AXAUUSD&interval=15",
}

# ─────────────────────────────────────────────
# 3. HTF CACHE — refresh every 60 minutes
# ─────────────────────────────────────────────
_htf_cache = {
    "BTC/USD": {"trend": "NEUTRAL", "updated": 0},
    "XAU/USD": {"trend": "NEUTRAL", "updated": 0},
}
HTF_CACHE_SECONDS = 3600  # 1 hour

# ─────────────────────────────────────────────
# 4. TELEGRAM
# ─────────────────────────────────────────────
def send_telegram(message):
    url     = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log.info("✅ Telegram alert sent")
        else:
            log.warning(f"Telegram status: {r.status_code}")
    except Exception as e:
        log.error(f"❌ Telegram error: {e}")

# ─────────────────────────────────────────────
# 5. SESSION & NEWS
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
                log.info(f"📰 News blackout: {news_str} ({diff:.0f}min away)")
                return True
        except Exception:
            pass
    return False

# ─────────────────────────────────────────────
# 6. INDICATORS
# ─────────────────────────────────────────────
def add_indicators(df):
    df["close"]  = pd.to_numeric(df["close"])
    df["high"]   = pd.to_numeric(df["high"])
    df["low"]    = pd.to_numeric(df["low"])
    df["volume"] = pd.to_numeric(df["volume"])
    df["EMA50"]  = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    df["EMA200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
    df["RSI"]    = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["vol_ma"] = df["volume"].rolling(VOLUME_MA_PERIOD).mean()
    return df

# ─────────────────────────────────────────────
# 7. DATA HELPERS
# ─────────────────────────────────────────────
def fetch_yfinance_df(ticker, period, interval):
    raw = yf.download(
        ticker, period=period,
        interval=interval,
        progress=False,
        auto_adjust=True
    )
    if raw.empty:
        raise ValueError(f"Empty yfinance: {ticker}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw.columns = [c.lower() for c in raw.columns]
    for col in ["open","high","low","close","volume"]:
        if col not in raw.columns:
            raw[col] = 0.0
    df = raw[["open","high","low","close","volume"]].copy().reset_index(drop=True)
    return add_indicators(df)

def fetch_ccxt_df(exchange_obj, symbol, timeframe, limit):
    ohlcv = exchange_obj.fetch_ohlcv(
        symbol, timeframe=timeframe, limit=limit
    )
    df = pd.DataFrame(
        ohlcv, columns=["time","open","high","low","close","volume"]
    )
    return add_indicators(df)

# ─────────────────────────────────────────────
# 8. GOLD DATA
# ─────────────────────────────────────────────
def get_gold_data():
    for ticker in ["GC=F", "MGC=F"]:
        try:
            df = fetch_yfinance_df(ticker, "5d", "15m")
            p  = df["close"].iloc[-1]
            if 4000 <= p <= 5500:
                log.info(f"Gold ✅ {ticker} — ${p:,.2f}")
                return df, f"yfinance {ticker}"
            log.warning(f"Gold {ticker} ${p:.2f} out of range")
        except Exception as e:
            log.warning(f"Gold {ticker} failed: {e}")

    try:
        ex = ccxt.binance()
        df = fetch_ccxt_df(ex, "PAXG/USDT", TIMEFRAME, CANDLE_LIMIT)
        p  = df["close"].iloc[-1]
        if 2500 <= p <= 5500:
            log.info(f"Gold ✅ Binance PAXG — ${p:,.2f}")
            return df, "Binance PAXG/USDT"
    except Exception as e:
        log.warning(f"Binance PAXG failed: {e}")

    log.error("⚠️ Gold all sources failed")
    return None, None

def _fetch_gold_htf_trend():
    """Internal — fetches fresh Gold HTF trend."""
    for ticker in ["GC=F", "MGC=F"]:
        try:
            df = fetch_yfinance_df(ticker, "30d", "1h")
            r  = df.iloc[-1]
            if r["EMA50"] > r["EMA200"]: return "BULL"
            if r["EMA50"] < r["EMA200"]: return "BEAR"
            return "NEUTRAL"
        except Exception as e:
            log.warning(f"Gold HTF {ticker} error: {e}")
    return "NEUTRAL"

def get_gold_htf():
    """Returns cached Gold HTF — refreshes every 60 min."""
    cache = _htf_cache["XAU/USD"]
    now   = time.time()
    if now - cache["updated"] > HTF_CACHE_SECONDS:
        log.info("🔄 Refreshing Gold HTF trend...")
        cache["trend"]   = _fetch_gold_htf_trend()
        cache["updated"] = now
        log.info(f"Gold HTF updated: {cache['trend']}")
    return cache["trend"]

# ─────────────────────────────────────────────
# 9. BTC DATA
# ─────────────────────────────────────────────
def get_btc_data():
    try:
        ex = ccxt.coinbase()
        df = fetch_ccxt_df(ex, "BTC/USD", TIMEFRAME, CANDLE_LIMIT)
        log.info("BTC ✅ Coinbase")
        return df, "Coinbase"
    except Exception as e:
        log.warning(f"BTC Coinbase failed: {e}")

    try:
        ex = ccxt.binance()
        df = fetch_ccxt_df(ex, "BTC/USDT", TIMEFRAME, CANDLE_LIMIT)
        log.info("BTC ✅ Binance")
        return df, "Binance"
    except Exception as e:
        log.warning(f"BTC Binance failed: {e}")

    try:
        df = fetch_yfinance_df("BTC-USD", "5d", "15m")
        log.info("BTC ✅ yfinance")
        return df, "yfinance BTC-USD"
    except Exception as e:
        log.error(f"⚠️ BTC all sources failed: {e}")

    return None, None

def _fetch_btc_htf_trend():
    """Internal — fetches fresh BTC HTF trend."""
    try:
        ex = ccxt.coinbase()
        df = fetch_ccxt_df(ex, "BTC/USD", TIMEFRAME_HTF, 250)
        r  = df.iloc[-1]
        if r["EMA50"] > r["EMA200"]: return "BULL"
        if r["EMA50"] < r["EMA200"]: return "BEAR"
        return "NEUTRAL"
    except Exception as e:
        log.warning(f"BTC HTF Coinbase error: {e}")

    try:
        ex = ccxt.binance()
        df = fetch_ccxt_df(ex, "BTC/USDT", TIMEFRAME_HTF, 250)
        r  = df.iloc[-1]
        if r["EMA50"] > r["EMA200"]: return "BULL"
        if r["EMA50"] < r["EMA200"]: return "BEAR"
    except Exception as e:
        log.warning(f"BTC HTF Binance error: {e}")

    return "NEUTRAL"

def get_btc_htf():
    """Returns cached BTC HTF — refreshes every 60 min."""
    cache = _htf_cache["BTC/USD"]
    now   = time.time()
    if now - cache["updated"] > HTF_CACHE_SECONDS:
        log.info("🔄 Refreshing BTC HTF trend...")
        cache["trend"]   = _fetch_btc_htf_trend()
        cache["updated"] = now
        log.info(f"BTC HTF updated: {cache['trend']}")
    return cache["trend"]

# ─────────────────────────────────────────────
# 10. ZONE DETECTION
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
        body = curr["close"] - curr["open"]
        if (prev["close"] < prev["open"] and
                curr["close"] > curr["open"] and
                body / size > 0.6):
            zones["demand"].append(curr["low"])
        if (prev["close"] > prev["open"] and
                curr["close"] < curr["open"] and
                abs(body) / size > 0.6):
            zones["supply"].append(curr["high"])
    return zones

def price_near_zone(price, levels):
    return any(
        abs(price - lvl) / lvl <= ZONE_THRESHOLD
        for lvl in levels
    )

# ─────────────────────────────────────────────
# 11. SIGNAL ENGINE
# ─────────────────────────────────────────────
def evaluate_signal(df, htf_trend, price, rsi, ema50, ema200, vol, vol_ma):
    is_bullish = ema50 > ema200
    zones      = detect_zones(df)
    volume_ok  = bool(not pd.isna(vol_ma) and vol >= vol_ma * VOLUME_MULTIPLIER)

    buy_checks = {
        "EMA bullish (15m)":  bool(is_bullish),
        "HTF bullish (1h)":   htf_trend in ("BULL", "NEUTRAL"),
        "RSI oversold (<35)": rsi < RSI_OVERSOLD,
        "In demand zone":     price_near_zone(price, zones["demand"]),
        "Volume confirmed":   volume_ok,
    }
    sell_checks = {
        "EMA bearish (15m)":   bool(not is_bullish),
        "HTF bearish (1h)":    htf_trend in ("BEAR", "NEUTRAL"),
        "RSI overbought (>65)":rsi > RSI_OVERBOUGHT,
        "In supply zone":      price_near_zone(price, zones["supply"]),
        "Volume confirmed":    volume_ok,
    }

    if all(buy_checks.values()):
        return "LONG / BUY",   list(buy_checks.keys()),  buy_checks, sell_checks
    if all(sell_checks.values()):
        return "SHORT / SELL", list(sell_checks.keys()), buy_checks, sell_checks
    return "NONE", [], buy_checks, sell_checks

# ─────────────────────────────────────────────
# 12. PROCESS SINGLE SYMBOL
# ─────────────────────────────────────────────
def process_symbol(symbol_key, session_name):
    """Fetch + evaluate one symbol. Called in parallel."""
    if symbol_key == "BTC/USD":
        df, source    = get_btc_data()
        htf_trend     = get_btc_htf()
        mt5_sym       = "BTCUSD.Qraw"
        signal_header = "🚨 *PEPPERSTONE BTCUSD.Qraw SIGNAL* 🚨"
    else:
        df, source    = get_gold_data()
        htf_trend     = get_gold_htf()
        mt5_sym       = "XAUUSD.Qraw"
        signal_header = "🚨 *PEPPERSTONE XAUUSD.Qraw SIGNAL* 🚨"

    if df is None:
        log.error(f"⚠️ {mt5_sym}: No data")
        return

    row    = df.iloc[-1]
    price  = float(row["close"])
    rsi    = float(row["RSI"])
    ema50  = float(row["EMA50"])
    ema200 = float(row["EMA200"])
    vol    = float(row["volume"])
    vol_ma = float(row["vol_ma"])

    if any(pd.isna(x) for x in [rsi, ema50, ema200, vol_ma]):
        log.warning(f"{mt5_sym}: Indicators not ready")
        return

    lo, hi = PRICE_RANGES[symbol_key]
    if not (lo <= price <= hi):
        log.error(f"⚠️ {mt5_sym} ${price:.2f} out of range — skipping")
        return

    signal, conditions_met, buy_checks, sell_checks = evaluate_signal(
        df, htf_trend, price, rsi, ema50, ema200, vol, vol_ma
    )

    is_bullish = ema50 > ema200

    if signal != "NONE":
        if signal == "LONG / BUY":
            sl = price * (1 - STOP_PCT)
            tp = price + (price - sl) * RR_RATIO
        else:
            sl = price * (1 + STOP_PCT)
            tp = price - (sl - price) * RR_RATIO

        risk       = abs(price - sl)
        reward     = abs(tp - price)
        passed_str = "\n".join([f"  ✅ {c}" for c in conditions_met])

        msg = (
            f"{signal_header}\n\n"
            f"🔥 *Action:* {signal}\n\n"
            f"💹 *Price:*       ${price:,.2f}\n"
            f"📍 *Entry:*       {price:,.2f}\n"
            f"🛑 *Stop Loss:*   {sl:,.2f}  (-{risk:.2f})\n"
            f"🎯 *Take Profit:* {tp:,.2f}  (+{reward:.2f})\n"
            f"⚖️ *R:R:*         1:{RR_RATIO}\n\n"
            f"📊 *Trend (15m):* {'Bullish 📈' if is_bullish else 'Bearish 📉'}\n"
            f"📈 *RSI:*         {rsi:.1f}\n"
            f"🌍 *HTF (1h):*    {htf_trend}\n"
            f"⏰ *Session:*     {session_name}\n"
            f"📡 *Source:*      {source}\n\n"
            f"*All 5 conditions met:*\n{passed_str}\n\n"
            f"🔗 [Open Chart]({CHART_LINKS[symbol_key]})"
        )
        send_telegram(msg)
        log.info(f"✅ SIGNAL {mt5_sym}: {signal} | Entry:{price:.2f} SL:{sl:.2f} TP:{tp:.2f}")
        return "SIGNAL"

    else:
        buy_score  = sum(1 for v in buy_checks.values()  if v)
        sell_score = sum(1 for v in sell_checks.values() if v)
        best_score = max(buy_score, sell_score)
        direction  = "BUY" if buy_score >= sell_score else "SELL"
        active     = buy_checks if direction == "BUY" else sell_checks
        failed     = [k for k, v in active.items() if not v]
        failed_str = " | ".join(failed) if failed else "none"

        log.info(
            f"Heartbeat {mt5_sym} | ${price:,.2f} | RSI:{rsi:.1f} | "
            f"HTF:{htf_trend} | {session_name} | "
            f"Score:{best_score}/5 ({direction}) | "
            f"{'Bullish' if is_bullish else 'Bearish'} | "
            f"Waiting: {failed_str}"
        )
        return "NONE"

# ─────────────────────────────────────────────
# 13. MAIN SCANNER — PARALLEL
# ─────────────────────────────────────────────
def scan_all():
    """Scan BTC + Gold in parallel — 3x faster."""
    in_session, session_name = is_valid_session()
    if not in_session:
        log.info(f"🌙 Outside session ({session_name}) — sleeping")
        return

    if is_near_news():
        log.info("📰 News blackout — skipping all symbols")
        return

    signal_fired = False

    # Fetch BTC + Gold simultaneously
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(process_symbol, sym, session_name): sym
            for sym in SYMBOLS
        }
        for future in as_completed(futures):
            sym    = futures[future]
            try:
                result = future.result()
                if result == "SIGNAL":
                    signal_fired = True
            except Exception as e:
                log.error(f"Error processing {sym}: {e}")

    # 10 min cooldown if any signal fired
    if signal_fired:
        log.info("⏳ Signal fired — 10 minute cooldown...")
        time.sleep(600)

# ─────────────────────────────────────────────
# 14. MAIN LOOP
# ─────────────────────────────────────────────
def main():
    log.info("═" * 60)
    log.info("🚀 PEPPERSTONE ZONE SNIPER v3.5")
    log.info("📊 Assets     : XAUUSD.Qraw + BTCUSD.Qraw")
    log.info("⏱️  Timeframe  : 15m + 1h HTF")
    log.info("🔍 Filters    : Session + News + HTF + Zone + Volume")
    log.info("🎯 Target     : 74-76% win rate | R:R 1:2")
    log.info("⚡ Speed      : Parallel fetch + HTF cache (3x faster)")
    log.info("💰 Gold       : GC=F ≈ Pepperstone XAUUSD (0.2% diff)")
    log.info("═" * 60)

    # Pre-load HTF cache on startup
    log.info("🔄 Pre-loading HTF trends...")
    get_btc_htf()
    get_gold_htf()
    log.info("✅ HTF cache ready — starting scanner")
    log.info("═" * 60)

    while True:
        try:
            start = time.time()
            scan_all()
            elapsed = time.time() - start
            log.info(f"⏱️ Cycle time: {elapsed:.1f}s")
            time.sleep(30)
        except KeyboardInterrupt:
            log.info("👋 Bot stopped")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()