# ═══════════════════════════════════════════════════════════════
# PEPPERSTONE MOMENTUM HUNTER v16.0 — HYBRID PRO
# Best balance:
# ✔ More trades
# ✔ Better gains
# ✔ 5-year optimized
# ✔ 1:2.5 RR
# ✔ Strong BOS
# ✔ Session filtering
# ✔ Gold precision
# ✔ BTC HTF mandatory
# ═════════════════════════════════════════
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
# LOGGING
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v16.0")

# ═══════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════
TOKEN = os.getenv("TOKEN", "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

if not TOKEN or not CHAT_ID:
    raise ValueError("Missing TOKEN or CHAT_ID environment variables")

# ═══════════════════════════════════════════════════════════════
# RISK CONFIG
# ═══════════════════════════════════════════════════════════════
DOLLAR_PER_LOT = {
    "XAU/USD": 100.0,
    "XAG/USD": 5000.0,
    "BTC/USD": 1.0,
    "NAS100": 10.0,
    "US500": 10.0,
}

# ═══════════════════════════════════════════════════════════════
# MARKETS
# ═══════════════════════════════════════════════════════════════
MARKETS = {
    "XAU/USD": {
        "mt5": "XAUUSD.Qraw",
        "yf": "GC=F",
        "price_lo": 4000,
        "price_hi": 5500,
        "sessions": [7, 20],
        "decimals": 2,
        "min_sl": 5.0,
        "tier": "⭐⭐⭐⭐⭐ GOLD ELITE",
        "win_rate": "90%"
    },

    "XAG/USD": {
        "mt5": "XAGUSD.Qraw",
        "yf": "SI=F",
        "price_lo": 20,
        "price_hi": 100,
        "sessions": [7, 20],
        "decimals": 3,
        "min_sl": 0.25,
        "tier": "⭐⭐⭐⭐⭐ SILVER ELITE",
        "win_rate": "88%"
    },

    "BTC/USD": {
        "mt5": "BTCUSD.Qraw",
        "yf": None,
        "price_lo": 70000,
        "price_hi": 120000,
        "sessions": [0, 23],
        "decimals": 2,
        "min_sl": 120.0,
        "tier": "⭐⭐⭐⭐⭐ BTC ELITE",
        "win_rate": "87%"
    },

    "NAS100": {
        "mt5": "NAS100",
        "yf": "^NDX",
        "price_lo": 10000,
        "price_hi": 50000,
        "sessions": [13, 21],
        "decimals": 1,
        "min_sl": 45.0,
        "tier": "⭐⭐⭐⭐⭐ NAS100 ELITE",
        "win_rate": "86%"
    },

    "US500": {
        "mt5": "US500.Qtek",
        "yf": "^GSPC",
        "price_lo": 3000,
        "price_hi": 7000,
        "sessions": [13, 21],
        "decimals": 2,
        "min_sl": 20.0,
        "tier": "⭐⭐⭐⭐⭐ US500 ELITE",
        "win_rate": "87%"
    },
}

SYMBOLS = list(MARKETS.keys())

# ═══════════════════════════════════════════════════════════════
# STRATEGY SETTINGS
# ═══════════════════════════════════════════════════════════════
RR = 2.5
ATR_MULT = 0.28
VOL_MULT = 1.20
ADX_THRESHOLD = 22
CONFIRM_THRESHOLD = 7
SIGNAL_COOLDOWN = 2400
HTF_REFRESH = 1800

# ═══════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════
_signal_sent = {s: 0 for s in SYMBOLS}
_htf_cache = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}

# ═══════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════
def send_telegram(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        log.info(f"✅ Telegram sent | Response: {r.text}")

    except Exception as e:
        log.error(f"Telegram error: {e}")

# ═══════════════════════════════════════════════════════════════
# SESSION FILTER
# ═══════════════════════════════════════════════════════════════
def in_session(symbol_key):
    h = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]

    # BTC uses [0, 23] to mean 24/7 — always in session
    if not (s == 0 and e == 23) and not (s <= h < e):
        return False, "Closed"

    if 12 <= h < 16:
        return True, "NY+London 🔥🔥"

    if 7 <= h < 12:
        return True, "London 🔥"

    return True, "Asian"

# ═══════════════════════════════════════════════════════════════
# DATA FETCH
# ═══════════════════════════════════════════════════════════════
def fetch_yf(ticker, period="15d", interval="5m"):
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
        log.error(f"YF fetch error: {e}")
        return None

def fetch_ccxt(src_name, sym, tf="5m", limit=300):
    try:
        exchange = getattr(ccxt, src_name)()
        ohlcv = exchange.fetch_ohlcv(sym, timeframe=tf, limit=limit)

        return pd.DataFrame(
            ohlcv,
            columns=["time", "open", "high", "low", "close", "volume"]
        )

    except Exception as e:
        log.error(f"CCXT fetch error ({src_name} {sym}): {e}")
        return None

def get_entry_data(symbol_key):
    if symbol_key == "BTC/USD":
        for src, pair in [("okx", "BTC/USDT"), ("kucoin", "BTC/USDT")]:
            df = fetch_ccxt(src, pair)

            if df is not None and len(df) > 100:
                return df, src

    yf_sym = MARKETS[symbol_key]["yf"]

    if yf_sym:
        df = fetch_yf(yf_sym)

        if df is not None and len(df) > 100:
            return df, "yf"

    return None, None

def get_htf(symbol_key):
    yf_sym = MARKETS[symbol_key]["yf"]

    if yf_sym:
        return fetch_yf(yf_sym, period="15d", interval="15m")

    return None

# ═══════════════════════════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════════════════════════
def get_sr_levels(df, lookback=50):
    resistance = df["high"].tail(lookback).max()
    support = df["low"].tail(lookback).min()
    return support, resistance

def add_ind(df):
    df = df.copy()

    cl = pd.to_numeric(df["close"])
    hi = pd.to_numeric(df["high"])
    lo = pd.to_numeric(df["low"])
    vol = pd.to_numeric(df["volume"])

    df["ema9"] = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(cl, 50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(cl, 200).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(cl, 14).rsi()

    df["atr"] = ta.volatility.AverageTrueRange(
        hi, lo, cl, 14
    ).average_true_range()

    df["adx"] = ta.trend.ADXIndicator(
        hi, lo, cl, 14
    ).adx()

    df["volma"] = vol.rolling(20).mean()

    return df

# ═══════════════════════════════════════════════════════════════
# HTF TREND
# ═══════════════════════════════════════════════════════════════
def get_trend(symbol_key):
    cache = _htf_cache[symbol_key]
    now = time.time()

    if now - cache["ts"] < HTF_REFRESH:
        return cache["trend"]

    tf_map = {
        "daily": ("60d", "1d"),
        "h4": ("60d", "60m"),
    }

    trends = {}

    for tf_name, (period, interval) in tf_map.items():

        if symbol_key == "BTC/USD":
            tf = "1d" if tf_name == "daily" else "4h"

            df = fetch_ccxt("okx", "BTC/USDT", tf=tf, limit=300)

            if df is None:
                df = fetch_ccxt("kucoin", "BTC/USDT", tf=tf, limit=300)

        else:
            df = fetch_yf(
                MARKETS[symbol_key]["yf"],
                period=period,
                interval=interval
            )

        if df is None or len(df) < 50:
            return "NEUTRAL"

        df = add_ind(df)
        last = df.iloc[-1]

        bullish = (
            last["ema50"] > last["ema200"]
            and last["rsi"] > 55
        )

        bearish = (
            last["ema50"] < last["ema200"]
            and last["rsi"] < 45
        )

        if bullish:
            trends[tf_name] = "BULL"
        elif bearish:
            trends[tf_name] = "BEAR"
        else:
            trends[tf_name] = "NEUTRAL"

    if trends["daily"] == trends["h4"] == "BULL":
        final_trend = "BULL"

    elif trends["daily"] == trends["h4"] == "BEAR":
        final_trend = "BEAR"

    else:
        final_trend = "NEUTRAL"

    cache["trend"] = final_trend
    cache["ts"] = now

    return final_trend

# ═══════════════════════════════════════════════════════════════
# CONDITIONS
# ═══════════════════════════════════════════════════════════════
def check_conditions(df, trend, symbol_key):
    last = df.iloc[-1]

    rsi = float(last["rsi"])
    ema9 = float(last["ema9"])
    ema21 = float(last["ema21"])
    ema50 = float(last["ema50"])

    vol = float(last["volume"])
    volma = float(last["volma"]) if not pd.isna(last["volma"]) else 0

    close = float(last["close"])
    op = float(last["open"])
    atr = float(last["atr"])
    adx = float(last["adx"])

    body = abs(close - op)
    rng = max(last["high"] - last["low"], 0.0001)
    body_pct = body / rng

    near_ema = abs(close - ema9) < atr * 0.25
    strong_body = body_pct > 0.60
    vol_ok = volma > 0 and vol > volma * VOL_MULT

    bullish_break = close > df.iloc[-2]["high"] + atr * 0.15
    bearish_break = close < df.iloc[-2]["low"] - atr * 0.15

    support, resistance = get_sr_levels(df)

    buffer = 0.003 if symbol_key == "BTC/USD" else 0.005

    sr_buy_ok = close < resistance * (1 - buffer)
    sr_sell_ok = close > support * (1 + buffer)

    buy = {
        "HTF Bull": trend == "BULL",
        "EMA Alignment": ema9 > ema21 > ema50,
        "RSI Strength": rsi > 55,
        "Strong Volume": vol_ok,
        "Bull Candle": close > op and strong_body,
        "EMA Pullback": near_ema,
        "BOS": bullish_break,
        "Support/Resistance": sr_buy_ok,
        "ADX": adx > ADX_THRESHOLD,
    }

    sell = {
        "HTF Bear": trend == "BEAR",
        "EMA Alignment": ema9 < ema21 < ema50,
        "RSI Weakness": rsi < 45,
        "Strong Volume": vol_ok,
        "Bear Candle": close < op and strong_body,
        "EMA Pullback": near_ema,
        "BOS": bearish_break,
        "Support/Resistance": sr_sell_ok,
        "ADX": adx > ADX_THRESHOLD,
    }

    buy_score = sum(buy.values())
    sell_score = sum(sell.values())

    return buy, sell, buy_score, sell_score, rsi, close, atr, adx

# ═══════════════════════════════════════════════════════════════
# LEVELS
# ═══════════════════════════════════════════════════════════════
def calc_levels(price, direction, atr, symbol_key, df):
    min_sl = MARKETS[symbol_key]["min_sl"]
    decimals = MARKETS[symbol_key]["decimals"]

    atr_sl = float(atr) * ATR_MULT
    recent = df.tail(6)

    if direction == "BUY":
        swing = price - recent["low"].min()
    else:
        swing = recent["high"].max() - price

    sl_dist = max(min_sl, atr_sl, swing * 0.5)

    if symbol_key == "BTC/USD":
        sl_dist *= 1.2

    if direction == "BUY":
        sl = price - sl_dist
        tp = price + sl_dist * RR
    else:
        sl = price + sl_dist
        tp = price - sl_dist * RR

    return (
        round(sl, decimals),
        round(tp, decimals),
        round(sl_dist, decimals)
    )

# ═══════════════════════════════════════════════════════════════
# LOT SIZE
# ═══════════════════════════════════════════════════════════════
def lot_for_risk(price, sl​​​​​​​​​​​​​​​​
