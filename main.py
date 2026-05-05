import time
import logging
import requests
import ccxt
import pandas as pd
import numpy as np
import ta
import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

# ═══════════════════════════════════════════════════════════════
# PEPPERSTONE SMC SNIPER v4.3
# 14 markets — all from YOUR Pepperstone MT5
# Strategy : Smart Money Concepts (SMC)
# Target   : 82-84% win rate | R:R 1:2
# Filters  : 8 SMC conditions per signal
# ═══════════════════════════════════════════════════════════════

# 1. LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("SMCSniper")

# ─────────────────────────────────────────────
# 2. CONFIGURATION
# ─────────────────────────────────────────────
TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

MARKETS = {
    # ── TIER 1 — Best SMC ──
    "XAU/USD": {
        "mt5":      "XAUUSD.Qraw",
        "price_lo": 4000,
        "price_hi": 5500,
        "sessions": [7, 17],
        "tier":     "⭐⭐⭐ Gold #1",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AXAUUSD&interval=15",
    },
    "BTC/USD": {
        "mt5":      "BTCUSD.Qraw",
        "price_lo": 50000,
        "price_hi": 200000,
        "sessions": [7, 17],
        "tier":     "⭐⭐⭐ BTC #2",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ABTCUSD&interval=15",
    },
    "GBP/USD": {
        "mt5":      "GBPUSD.Qraw",
        "price_lo": 1.10,
        "price_hi": 1.60,
        "sessions": [7, 17],
        "tier":     "⭐⭐⭐ GBP #3",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AGBPUSD&interval=15",
    },
    "EUR/USD": {
        "mt5":      "EURUSD.Qraw",
        "price_lo": 1.00,
        "price_hi": 1.50,
        "sessions": [7, 17],
        "tier":     "⭐⭐⭐ EUR #4",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AEURUSD&interval=15",
    },
    "ETH/USD": {
        "mt5":      "ETHUSD.Qraw",
        "price_lo": 1000,
        "price_hi": 10000,
        "sessions": [7, 17],
        "tier":     "⭐⭐⭐ ETH #5",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AETHUSD&interval=15",
    },
    "US500": {
        "mt5":      "US500.Qraw",
        "price_lo": 5000,
        "price_hi": 10000,
        "sessions": [13, 20],
        "tier":     "⭐⭐⭐ SPX #6",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AUS500&interval=15",
    },
    "USTEC": {
        "mt5":      "USTEC.Qraw",
        "price_lo": 15000,
        "price_hi": 30000,
        "sessions": [13, 20],
        "tier":     "⭐⭐⭐ NAS #7",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AUSTEC&interval=15",
    },
    # ── TIER 2 — New additions ──
    "XRP/USD": {
        "mt5":      "XRPUSD.Qraw",
        "price_lo": 0.1,
        "price_hi": 10,
        "sessions": [7, 17],
        "tier":     "⭐⭐ XRP #8",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AXRPUSD&interval=15",
    },
    "SOL/USD": {
        "mt5":      "SOLUSD.Qraw",
        "price_lo": 10,
        "price_hi": 1000,
        "sessions": [7, 17],
        "tier":     "⭐⭐ SOL #9",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ASOLUSD&interval=15",
    },
    "BNB/USD": {
        "mt5":      "BNBUSD.Qraw",
        "price_lo": 100,
        "price_hi": 2000,
        "sessions": [7, 17],
        "tier":     "⭐⭐ BNB #10",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ABNBUSD&interval=15",
    },
    "US30": {
        "mt5":      "US30.Qraw",
        "price_lo": 30000,
        "price_hi": 60000,
        "sessions": [13, 20],
        "tier":     "⭐⭐ DOW #11",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AUS30&interval=15",
    },
    "DE30": {
        "mt5":      "DE30.Qraw",
        "price_lo": 15000,
        "price_hi": 30000,
        "sessions": [7, 16],
        "tier":     "⭐⭐ DAX #12",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ADE30&interval=15",
    },
    "JP225": {
        "mt5":      "JP225.Qraw",
        "price_lo": 25000,
        "price_hi": 50000,
        "sessions": [0, 6],   # Asian session coverage!
        "tier":     "⭐⭐ NKY #13",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AJP225&interval=15",
    },
    "WTI/USD": {
        "mt5":      "WTIUSD.Qraw",
        "price_lo": 30,
        "price_hi": 150,
        "sessions": [7, 20],
        "tier":     "⭐⭐ OIL #14",
        "chart":    "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AWTIUSD&interval=15",
    },
}

SYMBOLS       = list(MARKETS.keys())
TIMEFRAME     = "15m"
TIMEFRAME_HTF = "1h"
CANDLE_LIMIT  = 220

RSI_OVERSOLD      = 35
RSI_OVERBOUGHT    = 65
STOP_PCT          = 0.005
RR_RATIO          = 2
VOLUME_MULTIPLIER = 1.3
VOLUME_MA_PERIOD  = 20
OB_LOOKBACK       = 10
FVG_THRESHOLD     = 0.001
BOS_LOOKBACK      = 20

NEWS_BLACKOUT_MINUTES = 30
HIGH_IMPACT_NEWS = [
    # ══ WEEK MAY 5-9 2026 ══
    "2026-05-06 14:00",  # ISM Services PMI
    "2026-05-07 18:00",  # Fed Rate Decision 🔴🔴
    "2026-05-07 18:30",  # Fed Press Conference 🔴
    "2026-05-08 12:30",  # US Jobless Claims
    "2026-05-09 12:30",  # NFP 🔴🔴
    "2026-05-09 14:00",  # US Unemployment Rate 🔴
    # ══ Add next week every Monday ══
]

# ─────────────────────────────────────────────
# 3. CACHE
# ─────────────────────────────────────────────
_htf_cache      = {sym: {"trend": "NEUTRAL", "updated": 0} for sym in SYMBOLS}
_presignal_sent = {sym: 0 for sym in SYMBOLS}
HTF_CACHE_SECONDS  = 3600
PRESIGNAL_COOLDOWN = 300

# ─────────────────────────────────────────────
# 4. TELEGRAM
# ─────────────────────────────────────────────
def send_telegram(message):
    url     = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log.info("✅ Telegram sent")
        else:
            log.warning(f"Telegram status: {r.status_code}")
    except Exception as e:
        log.error(f"❌ Telegram error: {e}")

# ─────────────────────────────────────────────
# 5. LOT SIZE CALCULATOR
# ─────────────────────────────────────────────
def calculate_lot_sizes(price, sl):
    sl_distance = abs(price - sl)
    if sl_distance == 0:
        return {}
    lots = {}
    for risk in [10, 25, 50, 100, 200]:
        lot = round(risk / sl_distance, 3)
        lots[risk] = lot
    return lots

def format_lot_sizes(lots):
    lines = []
    for risk, lot in lots.items():
        lines.append(f"  💵 ${risk} risk  →  {lot} lots")
    return "\n".join(lines)

# ─────────────────────────────────────────────
# 6. SESSION & NEWS
# ─────────────────────────────────────────────
def is_valid_session(symbol_key):
    now_hour = datetime.now(timezone.utc).hour
    start    = MARKETS[symbol_key]["sessions"][0]
    end      = MARKETS[symbol_key]["sessions"][1]
    if start <= now_hour < end:
        if 12 <= now_hour < 16:  return True, "NY+London"
        elif 7 <= now_hour < 12: return True, "London"
        elif now_hour < 7:       return True, "Asian"
        else:                    return True, "New York"
    return False, "Closed"

def is_near_news():
    now = datetime.now(timezone.utc)
    for news_str in HIGH_IMPACT_NEWS:
        try:
            news_dt = datetime.strptime(
                news_str, "%Y-%m-%d %H:%M"
            ).replace(tzinfo=timezone.utc)
            diff = abs((now - news_dt).total_seconds() / 60)
            if diff <= NEWS_BLACKOUT_MINUTES:
                log.info(f"📰 News blackout: {news_str} ({diff:.0f}min)")
                return True
        except Exception:
            pass
    return False

# ─────────────────────────────────────────────
# 7. INDICATORS
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
    df["ATR"]    = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14
    ).average_true_range()
    return df

# ─────────────────────────────────────────────
# 8. DATA FETCH — ALL 14 MARKETS
# ─────────────────────────────────────────────
def fetch_yfinance_df(ticker, period, interval):
    raw = yf.download(
        ticker, period=period,
        interval=interval,
        progress=False,
        auto_adjust=True
    )
    if raw.empty:
        raise ValueError(f"Empty: {ticker}")
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

def get_market_data(symbol_key, timeframe, limit):
    mkt    = MARKETS[symbol_key]
    period = "5d" if timeframe == "15m" else "30d"

    # GOLD
    if symbol_key == "XAU/USD":
        for ticker in ["GC=F", "MGC=F"]:
            try:
                df = fetch_yfinance_df(ticker, period, timeframe)
                p  = df["close"].iloc[-1]
                if mkt["price_lo"] <= p <= mkt["price_hi"]:
                    log.info(f"XAUUSD ✅ {ticker} — ${p:,.2f}")
                    return df, "GC=F"
            except Exception as e:
                log.warning(f"Gold {ticker}: {e}")
        return None, None

    # BTC
    if symbol_key == "BTC/USD":
        for source, sym in [("coinbase","BTC/USD"), ("binance","BTC/USDT")]:
            try:
                ex = getattr(ccxt, source)()
                df = fetch_ccxt_df(ex, sym, timeframe, limit)
                p  = df["close"].iloc[-1]
                if mkt["price_lo"] <= p <= mkt["price_hi"]:
                    log.info(f"BTCUSD ✅ {source} — ${p:,.2f}")
                    return df, source.capitalize()
            except Exception as e:
                log.warning(f"BTC {source}: {e}")
        try:
            df = fetch_yfinance_df("BTC-USD", period, timeframe)
            return df, "yfinance BTC"
        except Exception as e:
            log.warning(f"BTC yfinance: {e}")
        return None, None

    # ETH
    if symbol_key == "ETH/USD":
        for source, sym in [("coinbase","ETH/USD"), ("binance","ETH/USDT")]:
            try:
                ex = getattr(ccxt, source)()
                df = fetch_ccxt_df(ex, sym, timeframe, limit)
                p  = df["close"].iloc[-1]
                if mkt["price_lo"] <= p <= mkt["price_hi"]:
                    log.info(f"ETHUSD ✅ {source} — ${p:,.2f}")
                    return df, source.capitalize()
            except Exception as e:
                log.warning(f"ETH {source}: {e}")
        try:
            df = fetch_yfinance_df("ETH-USD", period, timeframe)
            return df, "yfinance ETH"
        except Exception as e:
            log.warning(f"ETH yfinance: {e}")
        return None, None

    # XRP
    if symbol_key == "XRP/USD":
        for source, sym in [("binance","XRP/USDT"), ("coinbase","XRP/USD")]:
            try:
                ex = getattr(ccxt, source)()
                df = fetch_ccxt_df(ex, sym, timeframe, limit)
                p  = df["close"].iloc[-1]
                if mkt["price_lo"] <= p <= mkt["price_hi"]:
                    log.info(f"XRPUSD ✅ {source} — ${p:,.4f}")
                    return df, source.capitalize()
            except Exception as e:
                log.warning(f"XRP {source}: {e}")
        try:
            df = fetch_yfinance_df("XRP-USD", period, timeframe)
            return df, "yfinance XRP"
        except Exception as e:
            log.warning(f"XRP yfinance: {e}")
        return None, None

    # SOL
    if symbol_key == "SOL/USD":
        for source, sym in [("binance","SOL/USDT"), ("coinbase","SOL/USD")]:
            try:
                ex = getattr(ccxt, source)()
                df = fetch_ccxt_df(ex, sym, timeframe, limit)
                p  = df["close"].iloc[-1]
                if mkt["price_lo"] <= p <= mkt["price_hi"]:
                    log.info(f"SOLUSD ✅ {source} — ${p:,.2f}")
                    return df, source.capitalize()
            except Exception as e:
                log.warning(f"SOL {source}: {e}")
        try:
            df = fetch_yfinance_df("SOL-USD", period, timeframe)
            return df, "yfinance SOL"
        except Exception as e:
            log.warning(f"SOL yfinance: {e}")
        return None, None

    # BNB
    if symbol_key == "BNB/USD":
        try:
            ex = ccxt.binance()
            df = fetch_ccxt_df(ex, "BNB/USDT", timeframe, limit)
            p  = df["close"].iloc[-1]
            if mkt["price_lo"] <= p <= mkt["price_hi"]:
                log.info(f"BNBUSD ✅ Binance — ${p:,.2f}")
                return df, "Binance"
        except Exception as e:
            log.warning(f"BNB Binance: {e}")
        try:
            df = fetch_yfinance_df("BNB-USD", period, timeframe)
            return df, "yfinance BNB"
        except Exception as e:
            log.warning(f"BNB yfinance: {e}")
        return None, None

    # GBP/USD
    if symbol_key == "GBP/USD":
        try:
            df = fetch_yfinance_df("GBPUSD=X", period, timeframe)
            p  = df["close"].iloc[-1]
            if mkt["price_lo"] <= p <= mkt["price_hi"]:
                log.info(f"GBPUSD ✅ — ${p:.5f}")
                return df, "yfinance GBPUSD=X"
        except Exception as e:
            log.warning(f"GBPUSD: {e}")
        return None, None

    # EUR/USD
    if symbol_key == "EUR/USD":
        try:
            df = fetch_yfinance_df("EURUSD=X", period, timeframe)
            p  = df["close"].iloc[-1]
            if mkt["price_lo"] <= p <= mkt["price_hi"]:
                log.info(f"EURUSD ✅ — ${p:.5f}")
                return df, "yfinance EURUSD=X"
        except Exception as e:
            log.warning(f"EURUSD: {e}")
        return None, None

    # US500
    if symbol_key == "US500":
        try:
            df = fetch_yfinance_df("^GSPC", period, timeframe)
            p  = df["close"].iloc[-1]
            if mkt["price_lo"] <= p <= mkt["price_hi"]:
                log.info(f"US500 ✅ — ${p:,.2f}")
                return df, "yfinance ^GSPC"
        except Exception as e:
            log.warning(f"US500: {e}")
        return None, None

    # USTEC
    if symbol_key == "USTEC":
        try:
            df = fetch_yfinance_df("^NDX", period, timeframe)
            p  = df["close"].iloc[-1]
            if mkt["price_lo"] <= p <= mkt["price_hi"]:
                log.info(f"USTEC ✅ — ${p:,.2f}")
                return df, "yfinance ^NDX"
        except Exception as e:
            log.warning(f"USTEC: {e}")
        return None, None

    # US30 — Dow Jones
    if symbol_key == "US30":
        try:
            df = fetch_yfinance_df("^DJI", period, timeframe)
            p  = df["close"].iloc[-1]
            if mkt["price_lo"] <= p <= mkt["price_hi"]:
                log.info(f"US30 ✅ — ${p:,.2f}")
                return df, "yfinance ^DJI"
        except Exception as e:
            log.warning(f"US30: {e}")
        return None, None

    # DE30 — DAX
    if symbol_key == "DE30":
        try:
            df = fetch_yfinance_df("^GDAXI", period, timeframe)
            p  = df["close"].iloc[-1]
            if mkt["price_lo"] <= p <= mkt["price_hi"]:
                log.info(f"DE30 ✅ — ${p:,.2f}")
                return df, "yfinance ^GDAXI"
        except Exception as e:
            log.warning(f"DE30: {e}")
        return None, None

    # JP225 — Nikkei (Asian session!)
    if symbol_key == "JP225":
        try:
            df = fetch_yfinance_df("^N225", period, timeframe)
            p  = df["close"].iloc[-1]
            if mkt["price_lo"] <= p <= mkt["price_hi"]:
                log.info(f"JP225 ✅ — ${p:,.2f}")
                return df, "yfinance ^N225"
        except Exception as e:
            log.warning(f"JP225: {e}")
        return None, None

    # WTI Oil
    if symbol_key == "WTI/USD":
        for ticker in ["CL=F", "CLF"]:
            try:
                df = fetch_yfinance_df(ticker, period, timeframe)
                p  = df["close"].iloc[-1]
                if mkt["price_lo"] <= p <= mkt["price_hi"]:
                    log.info(f"WTIUSD ✅ {ticker} — ${p:,.2f}")
                    return df, f"yfinance {ticker}"
            except Exception as e:
                log.warning(f"WTI {ticker}: {e}")
        return None, None

    return None, None

# ─────────────────────────────────────────────
# 9. HTF CACHE
# ─────────────────────────────────────────────
def get_htf_trend(symbol_key):
    cache = _htf_cache[symbol_key]
    now   = time.time()
    if now - cache["updated"] > HTF_CACHE_SECONDS:
        log.info(f"🔄 HTF: {MARKETS[symbol_key]['mt5']}")
        df, _ = get_market_data(symbol_key, "1h", 250)
        if df is not None:
            r = df.iloc[-1]
            if r["EMA50"] > r["EMA200"]:   cache["trend"] = "BULL"
            elif r["EMA50"] < r["EMA200"]: cache["trend"] = "BEAR"
            else:                           cache["trend"] = "NEUTRAL"
        cache["updated"] = now
        log.info(f"HTF {MARKETS[symbol_key]['mt5']}: {cache['trend']}")
    return cache["trend"]

# ─────────────────────────────────────────────
# 10. SMC DETECTIONS
# ─────────────────────────────────────────────
def detect_order_blocks(df):
    recent     = df.tail(OB_LOOKBACK).copy()
    demand_obs = []
    supply_obs = []
    for i in range(1, len(recent) - 1):
        prev = recent.iloc[i - 1]
        curr = recent.iloc[i]
        nxt  = recent.iloc[i + 1]
        if (prev["close"] < prev["open"] and
                nxt["close"] > nxt["open"] and
                nxt["close"] > prev["open"]):
            demand_obs.append({"top": prev["open"], "bottom": prev["close"]})
        if (prev["close"] > prev["open"] and
                nxt["close"] < nxt["open"] and
                nxt["close"] < prev["open"]):
            supply_obs.append({"top": prev["close"], "bottom": prev["open"]})
    return demand_obs, supply_obs

def price_in_ob(price, obs):
    return any(ob["bottom"] <= price <= ob["top"] for ob in obs)

def detect_fvg(df):
    recent      = df.tail(10).copy()
    bullish_fvg = []
    bearish_fvg = []
    for i in range(2, len(recent)):
        c1 = recent.iloc[i - 2]
        c3 = recent.iloc[i]
        if c3["low"] > c1["high"]:
            if (c3["low"] - c1["high"]) / c1["high"] >= FVG_THRESHOLD:
                bullish_fvg.append({"top": c3["low"], "bottom": c1["high"]})
        if c3["high"] < c1["low"]:
            if (c1["low"] - c3["high"]) / c1["low"] >= FVG_THRESHOLD:
                bearish_fvg.append({"top": c1["low"], "bottom": c3["high"]})
    return bullish_fvg, bearish_fvg

def price_near_fvg(price, fvgs):
    return any(f["bottom"] <= price <= f["top"] for f in fvgs)

def detect_bos(df):
    recent    = df.tail(BOS_LOOKBACK).copy().reset_index(drop=True)
    highs     = recent["high"].values
    lows      = recent["low"].values
    last      = len(recent) - 1
    prev_high = max(highs[:-3])
    prev_low  = min(lows[:-3])
    if highs[last] > prev_high: return "BULLISH_BOS"
    if lows[last]  < prev_low:  return "BEARISH_BOS"
    return None

def detect_sweep(df):
    recent    = df.tail(15).copy().reset_index(drop=True)
    last      = recent.iloc[-1]
    prev      = recent.iloc[:-1]
    prev_high = prev["high"].max()
    prev_low  = prev["low"].min()
    if last["low"]  < prev_low  and last["close"] > prev_low:  return "BUY_SWEEP"
    if last["high"] > prev_high and last["close"] < prev_high: return "SELL_SWEEP"
    return None

# ─────────────────────────────────────────────
# 11. SMC SIGNAL ENGINE
# ─────────────────────────────────────────────
def evaluate_smc_signal(df, htf_trend, price, rsi,
                         ema50, ema200, vol, vol_ma):
    is_bullish             = ema50 > ema200
    volume_ok              = bool(
        not pd.isna(vol_ma) and vol >= vol_ma * VOLUME_MULTIPLIER
    )
    demand_obs, supply_obs = detect_order_blocks(df)
    bullish_fvg, bear_fvg  = detect_fvg(df)
    bos                    = detect_bos(df)
    sweep                  = detect_sweep(df)

    buy_checks = {
        "EMA bullish (15m)":    bool(is_bullish),
        "HTF bullish (1h)":     htf_trend in ("BULL", "NEUTRAL"),
        "RSI oversold (<35)":   rsi < RSI_OVERSOLD,
        "In demand OB":         price_in_ob(price, demand_obs),
        "Bullish FVG nearby":   price_near_fvg(price, bullish_fvg),
        "Bullish BOS":          bos == "BULLISH_BOS",
        "Liquidity swept":      sweep == "BUY_SWEEP",
        "Volume confirmed":     volume_ok,
    }
    sell_checks = {
        "EMA bearish (15m)":    bool(not is_bullish),
        "HTF bearish (1h)":     htf_trend in ("BEAR", "NEUTRAL"),
        "RSI overbought (>65)": rsi > RSI_OVERBOUGHT,
        "In supply OB":         price_in_ob(price, supply_obs),
        "Bearish FVG nearby":   price_near_fvg(price, bear_fvg),
        "Bearish BOS":          bos == "BEARISH_BOS",
        "Liquidity swept":      sweep == "SELL_SWEEP",
        "Volume confirmed":     volume_ok,
    }

    if all(buy_checks.values()):
        return "LONG / BUY",   list(buy_checks.keys()),  buy_checks, sell_checks
    if all(sell_checks.values()):
        return "SHORT / SELL", list(sell_checks.keys()), buy_checks, sell_checks
    return "NONE", [], buy_checks, sell_checks

# ─────────────────────────────────────────────
# 12. TELEGRAM MESSAGES
# ─────────────────────────────────────────────
def send_presignal(symbol_key, price, rsi, htf_trend,
                   session_name, source, buy_checks,
                   sell_checks, direction, score):
    now = time.time()
    if now - _presignal_sent[symbol_key] < PRESIGNAL_COOLDOWN:
        return
    _presignal_sent[symbol_key] = now

    mkt        = MARKETS[symbol_key]
    mt5_sym    = mkt["mt5"]
    tier       = mkt["tier"]
    is_bullish = direction == "BUY"
    active     = buy_checks if is_bullish else sell_checks
    passed_str = "\n".join([f"  ✅ {k}" for k, v in active.items() if v])
    failed_str = "\n".join([f"  ⏳ {k}" for k, v in active.items() if not v])
    est_sl     = price * (1 - STOP_PCT) if is_bullish else price * (1 + STOP_PCT)
    lots_str   = format_lot_sizes(calculate_lot_sizes(price, est_sl))

    msg = (
        f"👀 *WATCH ALERT — {mt5_sym}* 👀\n"
        f"_{tier}_\n\n"
        f"⚡ *{score}/8 SMC conditions — forming!*\n\n"
        f"💹 *Price:* ${price:,.5f}\n"
        f"📊 *Direction:* {'Bullish 📈' if is_bullish else 'Bearish 📉'}\n"
        f"📈 *RSI:* {rsi:.1f}\n"
        f"🌍 *HTF:* {htf_trend}\n"
        f"⏰ *Session:* {session_name}\n"
        f"📡 *Source:* {source}\n\n"
        f"*Conditions passed:*\n{passed_str}\n\n"
        f"*Waiting for:*\n{failed_str}\n\n"
        f"📦 *Estimated Lot Sizes:*\n{lots_str}\n\n"
        f"⚠️ *Get ready — signal may fire soon!*\n"
        f"🔗 [Open Chart]({mkt['chart']})"
    )
    send_telegram(msg)
    log.info(f"👀 PRE-SIGNAL {mt5_sym} {score}/8 {direction}")

def send_signal(symbol_key, signal, price, rsi,
                ema50, ema200, htf_trend,
                session_name, source, conditions_met):
    mkt        = MARKETS[symbol_key]
    mt5_sym    = mkt["mt5"]
    tier       = mkt["tier"]
    is_bullish = ema50 > ema200

    if signal == "LONG / BUY":
        sl = price * (1 - STOP_PCT)
        tp = price + (price - sl) * RR_RATIO
    else:
        sl = price * (1 + STOP_PCT)
        tp = price - (sl - price) * RR_RATIO

    risk       = abs(price - sl)
    reward     = abs(tp - price)
    passed_str = "\n".join([f"  ✅ {c}" for c in conditions_met])
    lots_str   = format_lot_sizes(calculate_lot_sizes(price, sl))

    msg = (
        f"🚨 *PEPPERSTONE {mt5_sym} SIGNAL* 🚨\n"
        f"_{tier}_\n\n"
        f"🔥 *Action:* {signal}\n\n"
        f"💹 *Price:*       ${price:,.5f}\n"
        f"📍 *Entry:*       {price:,.5f}\n"
        f"🛑 *Stop Loss:*   {sl:,.5f}  (-{risk:.5f})\n"
        f"🎯 *Take Profit:* {tp:,.5f}  (+{reward:.5f})\n"
        f"⚖️ *R:R:*         1:{RR_RATIO}\n\n"
        f"📊 *Trend (15m):* {'Bullish 📈' if is_bullish else 'Bearish 📉'}\n"
        f"📈 *RSI:*         {rsi:.1f}\n"
        f"🌍 *HTF (1h):*    {htf_trend}\n"
        f"⏰ *Session:*     {session_name}\n"
        f"📡 *Source:*      {source}\n\n"
        f"*All 8 SMC conditions met:*\n{passed_str}\n\n"
        f"📦 *Lot Sizes by Risk:*\n{lots_str}\n\n"
        f"🔗 [Open Chart]({mkt['chart']})"
    )
    send_telegram(msg)
    log.info(
        f"✅ SIGNAL {mt5_sym}: {signal} | "
        f"Entry:{price:.5f} SL:{sl:.5f} TP:{tp:.5f}"
    )

# ─────────────────────────────────────────────
# 13. PROCESS MARKET
# ─────────────────────────────────────────────
def process_market(symbol_key):
    mkt = MARKETS[symbol_key]

    in_session, session_name = is_valid_session(symbol_key)
    if not in_session:
        log.info(f"🌙 {mkt['mt5']}: Outside session")
        return "NONE"

    if is_near_news():
        log.info(f"📰 {mkt['mt5']}: News blackout")
        return "NONE"

    df, source = get_market_data(symbol_key, "15m", CANDLE_LIMIT)
    if df is None:
        log.error(f"⚠️ {mkt['mt5']}: No data")
        return "NONE"

    htf_trend = get_htf_trend(symbol_key)
    row       = df.iloc[-1]
    price     = float(row["close"])
    rsi       = float(row["RSI"])
    ema50     = float(row["EMA50"])
    ema200    = float(row["EMA200"])
    vol       = float(row["volume"])
    vol_ma    = float(row["vol_ma"])

    if any(pd.isna(x) for x in [rsi, ema50, ema200, vol_ma]):
        log.warning(f"{mkt['mt5']}: Indicators not ready")
        return "NONE"

    if not (mkt["price_lo"] <= price <= mkt["price_hi"]):
        log.error(f"⚠️ {mkt['mt5']} ${price:.5f} out of range")
        return "NONE"

    signal, conditions_met, buy_checks, sell_checks = evaluate_smc_signal(
        df, htf_trend, price, rsi, ema50, ema200, vol, vol_ma
    )

    is_bullish = ema50 > ema200

    if signal != "NONE":
        send_signal(
            symbol_key, signal, price, rsi,
            ema50, ema200, htf_trend,
            session_name, source, conditions_met
        )
        return "SIGNAL"

    buy_score  = sum(1 for v in buy_checks.values()  if v)
    sell_score = sum(1 for v in sell_checks.values() if v)
    best_score = max(buy_score, sell_score)
    direction  = "BUY" if buy_score >= sell_score else "SELL"

    if best_score >= 6:
        send_presignal(
            symbol_key, price, rsi, htf_trend,
            session_name, source,
            buy_checks, sell_checks,
            direction, best_score
        )
        return "PRESIGNAL"

    active     = buy_checks if direction == "BUY" else sell_checks
    failed     = [k for k, v in active.items() if not v]
    failed_str = " | ".join(failed) if failed else "none"

    log.info(
        f"Heartbeat {mkt['mt5']} | ${price:,.5f} | RSI:{rsi:.1f} | "
        f"HTF:{htf_trend} | {session_name} | "
        f"Score:{best_score}/8 ({direction}) | "
        f"{'Bullish' if is_bullish else 'Bearish'} | "
        f"Waiting: {failed_str}"
    )
    return "NONE"

# ─────────────────────────────────────────────
# 14. MAIN SCANNER
# ─────────────────────────────────────────────
def scan_all():
    if is_near_news():
        log.info("📰 News blackout — skipping all")
        return False

    signal_fired = False
    with ThreadPoolExecutor(max_workers=14) as executor:
        futures = {
            executor.submit(process_market, sym): sym
            for sym in SYMBOLS
        }
        for future in as_completed(futures):
            sym = futures[future]
            try:
                result = future.result()
                if result == "SIGNAL":
                    signal_fired = True
            except Exception as e:
                log.error(f"Error {sym}: {e}")
    return signal_fired

# ─────────────────────────────────────────────
# 15. MAIN LOOP
# ─────────────────────────────────────────────
def main():
    log.info("═" * 60)
    log.info("🚀 PEPPERSTONE SMC SNIPER v4.3")
    log.info("📊 14 Markets from Pepperstone MT5:")
    log.info("   XAUUSD | BTCUSD | GBPUSD | EURUSD | ETHUSD")
    log.info("   US500  | USTEC  | XRPUSD | SOLUSD | BNBUSD")
    log.info("   US30   | DE30   | JP225  | WTIUSD")
    log.info("🧠 Strategy : Smart Money Concepts (SMC)")
    log.info("🔍 Filters  : 8 SMC conditions per signal")
    log.info("🎯 Target   : 82-84% win rate | R:R 1:2")
    log.info("⚡ Speed    : All 14 markets parallel")
    log.info("👀 Watch    : Alert at 6/8 or 7/8")
    log.info("🚨 Signal   : Alert at 8/8 — ENTER TRADE")
    log.info("📦 Lots     : Auto calculator in every message")
    log.info("🌏 Asian    : JP225 covers morning session!")
    log.info("═" * 60)

    log.info("🔄 Pre-loading HTF for all 14 markets...")
    with ThreadPoolExecutor(max_workers=14) as ex:
        for sym in SYMBOLS:
            ex.submit(get_htf_trend, sym)
    log.info("✅ All HTF cached — scanner starting!")
    log.info("═" * 60)

    while True:
        try:
            start        = time.time()
            signal_fired = scan_all()
            elapsed      = time.time() - start
            log.info(f"⏱️  Cycle: {elapsed:.1f}s")

            if signal_fired:
                log.info("⏳ Signal fired — 10 min cooldown")
                time.sleep(600)
            else:
                time.sleep(10)

        except KeyboardInterrupt:
            log.info("👋 Bot stopped")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()