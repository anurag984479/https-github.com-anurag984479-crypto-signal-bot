

# ============================================================
# PEPPERSTONE MOMENTUM HUNTER
# ULTIMATE-ICT-SUPREME-2026-ELITE
# XAU/USD + NAS100 + EUR/USD + GBP/JPY + BTC/USD
# ICT CONCEPT ENGINE — MSS + FVG + OB + MTF TREND
# ============================================================

import gc
import time
import logging
import requests
import pandas as pd
import ta
import os
import csv
from threading import Lock
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

SYSTEM_VERSION = "ULTIMATE-ICT-SUPREME-2026-ELITE"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("ULTIMATE-ICT-2026")

TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

session_http = requests.Session()
signal_lock  = Lock()
log_lock     = Lock()

PRIORITY_MARKETS = [
    "XAU/USD", "NAS100", "EUR/USD", "GBP/JPY", "BTC/USD",
]

SESSION_THRESHOLDS = {
    "London":      16,
    "NY Killzone": 16,
    "NY+London":   15,
}

RR_PROFILE = {
    "XAU/USD": {"TREND": 3.2, "BREAKOUT": 3.8, "RANGE": 2.4},
    "NAS100":  {"TREND": 3.0, "BREAKOUT": 3.5, "RANGE": 2.3},
    "EUR/USD": {"TREND": 2.6, "BREAKOUT": 3.0, "RANGE": 2.0},
    "GBP/JPY": {"TREND": 2.8, "BREAKOUT": 3.4, "RANGE": 2.1},
    "BTC/USD": {"TREND": 3.0, "BREAKOUT": 3.5, "RANGE": 2.5},
}

SCALP_ADX_MIN      = 14
SCALP_ADX_MAX      = 26
SCALP_RSI_BUY_MAX  = 38
SCALP_RSI_SELL_MIN = 62
SCALP_MIN_SCORE    = 8
SCALP_RR = {
    "XAU/USD": 2.0, "NAS100": 1.8, "EUR/USD": 1.8,
    "GBP/JPY": 2.0, "BTC/USD": 2.0,
}

MARKETS = {
    "XAU/USD": {
        "mt5": "XAUUSD.Qraw", "yf": "GC=F",
        "price_lo": 0, "price_hi": float("inf"),
        "sessions": [0, 20], "decimals": 2, "min_sl": 7.0,
        "tier": "GOLD ELITE", "bias": "BULL", "rr": 2.8,
        "sweep_bonus": 3, "wick_ratio": 1.8,
    },
    "NAS100": {
        "mt5": "NAS100", "yf": "^NDX",
        "price_lo": 0, "price_hi": float("inf"),
        "sessions": [0, 21], "decimals": 1, "min_sl": 55.0,
        "tier": "NASDAQ ELITE", "bias": "BULL", "rr": 2.7,
        "sweep_bonus": 2, "wick_ratio": 1.6,
    },
    "EUR/USD": {
        "mt5": "EURUSD", "yf": "EURUSD=X",
        "price_lo": 0, "price_hi": float("inf"),
        "sessions": [0, 24], "decimals": 5, "min_sl": 0.0012,
        "tier": "FOREX MAJOR ELITE", "bias": "BULL", "rr": 2.4,
        "sweep_bonus": 2, "wick_ratio": 1.4,
    },
    "GBP/JPY": {
        "mt5": "GBPJPY", "yf": "GBPJPY=X",
        "price_lo": 0, "price_hi": float("inf"),
        "sessions": [0, 24], "decimals": 3, "min_sl": 0.180,
        "tier": "FOREX VOLATILITY ELITE", "bias": "BULL", "rr": 2.7,
        "sweep_bonus": 3, "wick_ratio": 1.7,
    },
    "BTC/USD": {
        "mt5": "BTCUSD", "yf": "BTC-USD",
        "price_lo": 0, "price_hi": float("inf"),
        "sessions": [0, 24], "decimals": 2, "min_sl": 120.0,
        "tier": "CRYPTO ELITE", "bias": "BULL", "rr": 2.8,
        "sweep_bonus": 3, "wick_ratio": 1.8,
    },
}

SYMBOLS = ["XAU/USD", "NAS100", "EUR/USD", "GBP/JPY", "BTC/USD"]

ATR_MULT               = 0.28
VOL_MULT               = 1.25
ADX_THRESHOLD          = 26
SIGNAL_COOLDOWN        = 3600
HTF_REFRESH            = 900
MAX_DAILY_LOSS         = -300
MAX_CONSECUTIVE_LOSSES = 3
MAIN_LOOP_DELAY        = 4
STDV_PERIOD            = 20
STDV_THRESHOLD_MULT    = 1.15
AOX_FAST               = 5
AOX_SLOW               = 34

ENABLE_WIZARD_AI     = True
WIZARD_MIN_SCORE     = 18
WIZARD_VOLUME_MULT   = 1.5
WIZARD_ADX_THRESHOLD = 25

CORRELATION_BLOCK   = True
MAX_OPEN_CORRELATED = 2
VOLATILITY_KILL     = True
FALSE_BREAK_FILTER  = True

EXECUTION_BUFFER = {
    "XAU/USD": 0.20, "NAS100": 2.5, "EUR/USD": 0.00008,
    "GBP/JPY": 0.015, "BTC/USD": 5.0,
}

RANGE_MIN_SCORE = 9
TREND_MIN_SCORE = 10

# ============================================================
# BTC AGGRESSIVE MODE SETTINGS
# ============================================================
ENABLE_BTC_AGGRESSIVE_REVERSAL = True
BTC_REVERSAL_MIN_SCORE         = 10
BTC_REVERSAL_RR                = 3.5

ENABLE_BTC_BREAKDOWN_MODE      = True
BTC_BREAKDOWN_MIN_SCORE        = 9
BTC_BREAKDOWN_RR               = 3.2

MARKET_STRUCTURE = {
    "XAU/USD": {
        "sweep_lookback": 6, "zone_lookback": 10,
        "displacement_mult": 1.20, "premium_discount_lookback": 24,
        "wick_ratio": 1.8, "mss_lookback": 10,
        "ob_lookback": 8, "fvg_min_gap_mult": 0.3,
    },
    "NAS100": {
        "sweep_lookback": 8, "zone_lookback": 12,
        "displacement_mult": 1.35, "premium_discount_lookback": 30,
        "wick_ratio": 2.0, "mss_lookback": 12,
        "ob_lookback": 10, "fvg_min_gap_mult": 0.4,
    },
    "EUR/USD": {
        "sweep_lookback": 10, "zone_lookback": 14,
        "displacement_mult": 1.15, "premium_discount_lookback": 32,
        "wick_ratio": 1.4, "mss_lookback": 10,
        "ob_lookback": 8, "fvg_min_gap_mult": 0.2,
    },
    "GBP/JPY": {
        "sweep_lookback": 8, "zone_lookback": 12,
        "displacement_mult": 1.30, "premium_discount_lookback": 28,
        "wick_ratio": 1.8, "mss_lookback": 10,
        "ob_lookback": 8, "fvg_min_gap_mult": 0.3,
    },
    "BTC/USD": {
        "sweep_lookback": 8, "zone_lookback": 12,
        "displacement_mult": 1.25, "premium_discount_lookback": 28,
        "wick_ratio": 1.8, "mss_lookback": 10,
        "ob_lookback": 8, "fvg_min_gap_mult": 0.5,
    },
}

MARKET_MIN_STRUCTURE_SCORE = {
    "XAU/USD": 5, "NAS100": 7, "EUR/USD": 5, "GBP/JPY": 5, "BTC/USD": 6,
}

ALLOWED_SESSIONS = ["London", "NY Killzone", "NY+London", "24H"]

ATR_MARKET_MULTIPLIER = {
    "XAU/USD": 1.05, "NAS100": 1.03, "EUR/USD": 0.95,
    "GBP/JPY": 1.10, "BTC/USD": 1.10,
}

DOLLAR_PER_POINT = {
    "XAU/USD": 100, "NAS100": 10, "EUR/USD": 100000,
    "GBP/JPY": 1000, "BTC/USD": 1,
}

MAX_SPREAD = {
    "XAU/USD": 1.35, "NAS100": 5.0, "EUR/USD": 0.00035,
    "GBP/JPY": 0.060, "BTC/USD": 35.0,
}

REGIME_TIMEFRAME = {
    "SCALP": "1M / 5M", "RANGE": "15M / 30M",
    "TREND": "1H / 4H", "BREAKOUT": "15M / 1H",
}

MAX_SIGNALS_PER_DAY = {
    "XAU/USD": 3, "NAS100": 2, "EUR/USD": 2, "GBP/JPY": 2, "BTC/USD": 3,
}

CORRELATED_GROUPS = [["EUR/USD", "GBP/JPY"]]

# ============================================================
# STATE
# ============================================================
daily_pnl           = 0
consecutive_losses  = 0
last_reset_day      = datetime.now(timezone.utc).day

_signal_sent           = {s: 0 for s in SYMBOLS}
_htf_cache             = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}
_last_signal_direction = {}
_last_signal_time      = {}
_signal_counter        = {s: {"session": None, "count": 0} for s in SYMBOLS}
_daily_signal_count    = {s: 0 for s in SYMBOLS}

for _file in ["signals_log.csv", "signals_backup.csv"]:
    if not os.path.exists(_file):
        with open(_file, "a", encoding="utf-8"):
            pass

# ============================================================
# DAILY RESET
# ============================================================
def reset_daily():
    global daily_pnl, consecutive_losses, last_reset_day
    global _daily_signal_count, _htf_cache
    current_day = datetime.now(timezone.utc).day
    if current_day != last_reset_day:
        daily_pnl           = 0
        consecutive_losses  = 0
        last_reset_day      = current_day
        _daily_signal_count = {s: 0 for s in SYMBOLS}
        _htf_cache          = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}
        log.info("Daily reset complete")

def update_trade_result(pnl):
    global daily_pnl, consecutive_losses
    daily_pnl += pnl
    if pnl < 0:
        consecutive_losses += 1
    else:
        consecutive_losses = 0

def sync_real_pnl():
    return daily_pnl

# ============================================================
# WATCHDOG
# ============================================================
def watchdog():
    try:
        with open("heartbeat.txt", "w", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} | {SYSTEM_VERSION} | ACTIVE")
    except Exception as e:
        log.error(f"Watchdog failure: {e}")

# ============================================================
# LOG ROTATION
# ============================================================
def rotate_log():
    try:
        if os.path.isfile("signals_log.csv"):
            if os.path.getsize("signals_log.csv") > 5_000_000:
                os.rename("signals_log.csv", f"signals_log_{int(time.time())}.csv")
    except Exception as e:
        log.error(f"Log rotation failure: {e}")

# ============================================================
# SIGNAL LOGGER
# ============================================================
def log_signal(symbol, direction, score, rr, entry, sl, tp,
               session, regime, timeframe, signal_type):
    with log_lock:
        file_exists = os.path.isfile("signals_log.csv")
        with open("signals_log.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "version", "timestamp", "symbol", "direction",
                    "score", "rr", "entry", "sl", "tp",
                    "session", "regime", "timeframe", "signal_type"
                ])
            writer.writerow([
                SYSTEM_VERSION, datetime.now(timezone.utc).isoformat(),
                symbol, direction, score, rr,
                entry, sl, tp, session, regime, timeframe, signal_type
            ])
        try:
            with open("signals_backup.csv", "a", newline="", encoding="utf-8") as backup:
                csv.writer(backup).writerow([
                    SYSTEM_VERSION, datetime.now(timezone.utc).isoformat(),
                    symbol, direction, score, rr,
                    entry, sl, tp, session, regime, timeframe, signal_type
                ])
        except Exception as e:
            log.error(f"Backup log failed: {e}")

# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(msg):
    for attempt in range(3):
        try:
            r = session_http.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                timeout=8
            )
            if r.status_code != 200:
                log.error(f"Telegram HTTP {r.status_code} | {r.text}")
                time.sleep(2)
                continue
            log.info(f"Telegram sent | {r.text}")
            return True
        except Exception as e:
            log.error(f"Telegram error attempt {attempt + 1}: {e}")
            time.sleep(2)
    return False

# ============================================================
# CIRCUIT BREAKERS
# ============================================================
def weekend_block(symbol_key):
    return False

def daily_loss_lock():
    if daily_pnl <= MAX_DAILY_LOSS:
        log.info("Daily loss lock active")
        return True
    return False

def loss_streak_lock():
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        log.info("Kill switch: 3 consecutive losses")
        return True
    return False

# ============================================================
# DATA FETCHING
# ============================================================
def fetch_yf(ticker, period="15d", interval="5m"):
    for attempt in range(3):
        try:
            time.sleep(0.4)
            raw = yf.download(
                ticker, period=period, interval=interval,
                progress=False, auto_adjust=True, threads=False
            )
            if raw.empty:
                log.error(f"{ticker} returned empty data")
                time.sleep(1)
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw.columns = [str(c).lower() for c in raw.columns]
            if "volume" in raw.columns:
                if raw["volume"].sum() == 0:
                    raw["volume"] = 1000
            else:
                raw["volume"] = 1000
            required_cols = ["open", "high", "low", "close", "volume"]
            for col in required_cols:
                if col not in raw.columns:
                    raw[col] = 0
            df = raw[required_cols].copy()
            df = df.drop_duplicates()
            df = df.ffill()
            df = df.bfill()
            return df.reset_index(drop=True)
        except Exception as e:
            log.error(f"YFinance fetch failed {ticker} | Attempt {attempt+1} | {e}")
            time.sleep(1)
    return None

def fetch_market_data(symbol_key):
    yf_sym = MARKETS[symbol_key]["yf"]
    if symbol_key in ["EUR/USD", "GBP/JPY"]:
        df = fetch_yf(yf_sym, period="59d", interval="5m")
    elif symbol_key == "XAU/USD":
        df = fetch_yf(yf_sym, period="45d", interval="5m")
    elif symbol_key == "BTC/USD":
        df = fetch_yf(yf_sym, period="59d", interval="5m")
    else:
        df = fetch_yf(yf_sym, period="30d", interval="5m")
    if df is not None and len(df) > 150:
        df = df.drop_duplicates()
        df = df.reset_index(drop=True)
        return df
    return None

def get_entry_data(symbol_key):
    df = fetch_market_data(symbol_key)
    if df is not None:
        return df, "yf"
    return None, None

def get_spread(df):
    if df is None or len(df) < 3:
        return 999
    recent = df.tail(3)
    avg_range = (recent["high"].astype(float) - recent["low"].astype(float)).mean()
    return avg_range * 0.18

# ============================================================
# INDICATORS
# ============================================================
def add_ind(df):
    df  = df.copy()
    cl  = pd.to_numeric(df["close"],  errors="coerce")
    hi  = pd.to_numeric(df["high"],   errors="coerce")
    lo  = pd.to_numeric(df["low"],    errors="coerce")
    vol = pd.to_numeric(df["volume"], errors="coerce")

    df["ema9"]     = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"]    = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"]    = ta.trend.EMAIndicator(cl, 50).ema_indicator()
    df["ema200"]   = ta.trend.EMAIndicator(cl, 200).ema_indicator()
    df["rsi"]      = ta.momentum.RSIIndicator(cl, 14).rsi()
    df["atr"]      = ta.volatility.AverageTrueRange(hi, lo, cl, 14).average_true_range()
    df["adx"]      = ta.trend.ADXIndicator(hi, lo, cl, 14).adx()
    df["volma"]    = vol.rolling(20).mean()
    df["vwap"]     = (cl * vol).cumsum() / vol.cumsum()
    df["stdv"]     = cl.rolling(STDV_PERIOD).std()
    df["aox_fast"] = ta.trend.EMAIndicator(cl, AOX_FAST).ema_indicator()
    df["aox_slow"] = ta.trend.EMAIndicator(cl, AOX_SLOW).ema_indicator()
    df["aox"]      = df["aox_fast"] - df["aox_slow"]

    hlc3      = (hi + lo + cl) / 3
    esa       = hlc3.ewm(span=10, adjust=False).mean()
    d         = (hlc3 - esa).abs().ewm(span=10, adjust=False).mean()
    ci        = (hlc3 - esa) / (0.015 * d)
    df["wt1"] = ci.ewm(span=21, adjust=False).mean()
    df["wt2"] = df["wt1"].rolling(4).mean()

    df.replace([float("inf"), float("-inf")], pd.NA, inplace=True)
    df.ffill(inplace=True)
    df.dropna(inplace=True)
    return df

# ============================================================
# ICT — MSS
# ============================================================
def detect_mss(df, symbol_key):
    lookback = MARKET_STRUCTURE[symbol_key]["mss_lookback"]
    if len(df) < lookback + 3:
        return False, False
    recent        = df.tail(lookback + 3)
    closes        = recent["close"].values
    highs         = recent["high"].values
    lows          = recent["low"].values
    swing_high    = float(highs[:-2].max())
    swing_low     = float(lows[:-2].min())
    current_close = float(closes[-1])
    prev_close    = float(closes[-2])
    atr           = float(df.iloc[-1]["atr"])
    bullish_mss   = prev_close < swing_high and current_close > swing_high + atr * 0.05
    bearish_mss   = prev_close > swing_low  and current_close < swing_low  - atr * 0.05
    return bullish_mss, bearish_mss

# ============================================================
# ICT — FVG
# ============================================================
def detect_fvg(df, symbol_key):
    if len(df) < 3:
        return False, False, None, None
    atr     = float(df.iloc[-1]["atr"])
    min_gap = atr * MARKET_STRUCTURE[symbol_key]["fvg_min_gap_mult"]
    c1_high = float(df.iloc[-3]["high"])
    c1_low  = float(df.iloc[-3]["low"])
    c3_high = float(df.iloc[-1]["high"])
    c3_low  = float(df.iloc[-1]["low"])
    bull_fvg = (c1_high < c3_low)  and ((c3_low  - c1_high) >= min_gap)
    bear_fvg = (c1_low  > c3_high) and ((c1_low  - c3_high) >= min_gap)
    fvg_high = c3_low  if bull_fvg else (c1_low  if bear_fvg else None)
    fvg_low  = c1_high if bull_fvg else (c3_high if bear_fvg else None)
    return bull_fvg, bear_fvg, fvg_high, fvg_low

# ============================================================
# ICT — ORDER BLOCK
# ============================================================
def detect_order_block(df, symbol_key):
    lookback = MARKET_STRUCTURE[symbol_key]["ob_lookback"]
    if len(df) < lookback + 2:
        return False, False, None, None
    atr    = float(df.iloc[-1]["atr"])
    price  = float(df.iloc[-1]["close"])
    recent = df.tail(lookback + 2)
    bull_ob = bear_ob = False
    ob_high = ob_low = None
    for i in range(len(recent) - 3, 1, -1):
        candle  = recent.iloc[i]
        next_c  = recent.iloc[i + 1]
        next_c2 = recent.iloc[i + 2] if i + 2 < len(recent) else next_c
        c_open = float(candle["open"]); c_close = float(candle["close"])
        n_close = float(next_c["close"]); n2_close = float(next_c2["close"])
        if c_close < c_open:
            if (n2_close - n_close) > atr * 0.8:
                if float(candle["low"]) <= price <= float(candle["high"]) * 1.002:
                    bull_ob = True; ob_high = float(candle["high"]); ob_low = float(candle["low"]); break
    for i in range(len(recent) - 3, 1, -1):
        candle  = recent.iloc[i]
        next_c  = recent.iloc[i + 1]
        next_c2 = recent.iloc[i + 2] if i + 2 < len(recent) else next_c
        c_open = float(candle["open"]); c_close = float(candle["close"])
        n_close = float(next_c["close"]); n2_close = float(next_c2["close"])
        if c_close > c_open:
            if (n_close - n2_close) > atr * 0.8:
                if float(candle["low"]) * 0.998 <= price <= float(candle["high"]):
                    bear_ob = True; ob_high = float(candle["high"]); ob_low = float(candle["low"]); break
    return bull_ob, bear_ob, ob_high, ob_low

# ============================================================
# ICT — MTF TREND
# ============================================================
def ict_mtf_trend(df):
    trends = {"5M": "NEUTRAL", "1H": "NEUTRAL", "4H": "NEUTRAL", "12H": "NEUTRAL"}
    if len(df) < 50:
        return trends
    last  = df.iloc[-1]
    close = float(last["close"])
    ema9  = float(last["ema9"])
    ema21 = float(last["ema21"])
    if ema9 > ema21:   trends["5M"] = "BULLISH"
    elif ema9 < ema21: trends["5M"] = "BEARISH"
    if len(df) >= 14:
        ma = df["close"].rolling(12).mean().iloc[-1]
        if not pd.isna(ma): trends["1H"] = "BULLISH" if close > ma else "BEARISH"
    if len(df) >= 50:
        ma = df["close"].rolling(48).mean().iloc[-1]
        if not pd.isna(ma): trends["4H"] = "BULLISH" if close > ma else "BEARISH"
    if len(df) >= 150:
        ma = df["close"].rolling(144).mean().iloc[-1]
        if not pd.isna(ma): trends["12H"] = "BULLISH" if close > ma else "BEARISH"
    return trends

def ict_trend_aligned(trends, direction):
    target = "BULLISH" if direction == "BUY" else "BEARISH"
    return sum(1 for v in trends.values() if v == target) >= 3

def ict_trend_score(trends, direction):
    target = "BULLISH" if direction == "BUY" else "BEARISH"
    return sum(1 for v in trends.values() if v == target)

# ============================================================
# SMART AI SHORT TERM TREND
# ============================================================
def smart_ai_short_term_trend(df):
    if df is None or len(df) < 50:
        return "NEUTRAL"
    last = df.iloc[-1]
    ema9 = float(last["ema9"]); ema21 = float(last["ema21"])
    aox  = float(last["aox"]);  wt1   = float(last["wt1"]); wt2 = float(last["wt2"])
    if ema9 > ema21 and aox > 0 and wt1 > wt2: return "BULLISH"
    if ema9 < ema21 and aox < 0 and wt1 < wt2: return "BEARISH"
    return "NEUTRAL"

# ============================================================
# LIQUIDITY SWEEP
# ============================================================
def detect_liquidity_sweep(df, symbol_key):
    lookback = MARKET_STRUCTURE[symbol_key]["sweep_lookback"]
    if len(df) < lookback:
        return False, False
    recent    = df.tail(lookback)
    prev_high = float(recent["high"].iloc[:-1].max())
    prev_low  = float(recent["low"].iloc[:-1].min())
    last      = recent.iloc[-1]
    return (
        float(last["low"])  < prev_low  and float(last["close"]) > prev_low,
        float(last["high"]) > prev_high and float(last["close"]) < prev_high
    )

# ============================================================
# WICK REJECTION
# ============================================================
def detect_wick_rejection(df, atr, symbol_key):
    if len(df) < 2:
        return False, False
    candle = df.iloc[-1]
    open_p = float(candle["open"]); close_p = float(candle["close"])
    high_p = float(candle["high"]); low_p   = float(candle["low"])
    body   = abs(close_p - open_p)
    if body < atr * 0.05:
        return False, False
    upper_wick = high_p - max(open_p, close_p)
    lower_wick = min(open_p, close_p) - low_p
    wr         = MARKETS[symbol_key]["wick_ratio"]
    return lower_wick > body * wr, upper_wick > body * wr

# ============================================================
# ELITE STRONG CANDLE
# ============================================================
def elite_strong_candle(df, direction):
    if len(df) < 2:
        return False
    candle      = df.iloc[-1]
    open_p      = float(candle["open"]);  close_p = float(candle["close"])
    high_p      = float(candle["high"]);  low_p   = float(candle["low"])
    body        = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0 or body / total_range < 0.70:
        return False
    if direction == "BUY":
        return close_p > open_p and close_p >= high_p - total_range * 0.15
    if direction == "SELL":
        return close_p < open_p and close_p <= low_p + total_range * 0.15
    return False

# ============================================================
# PREMIUM / DISCOUNT ZONES
# ============================================================
def premium_discount(df, symbol_key):
    lookback = MARKET_STRUCTURE[symbol_key]["premium_discount_lookback"]
    if len(df) < lookback:
        return {"discount": False, "premium": False}
    recent   = df.tail(lookback)
    midpoint = (float(recent["high"].max()) + float(recent["low"].min())) / 2
    price    = float(df.iloc[-1]["close"])
    return {"discount": price < midpoint, "premium": price > midpoint}

# ============================================================
# ZONE RETEST
# ============================================================
def detect_zone_retest(df, symbol_key, direction):
    lookback = MARKET_STRUCTURE[symbol_key]["zone_lookback"]
    if len(df) < lookback:
        return False
    recent  = df.tail(lookback)
    current = df.iloc[-1]
    if direction == "BUY":
        return float(current["low"]) <= float(recent["low"].min()) * 1.002
    if direction == "SELL":
        return float(current["high"]) >= float(recent["high"].max()) * 0.998
    return False

# ============================================================
# DISPLACEMENT
# ============================================================
def detect_displacement(df, symbol_key):
    if len(df) < 2:
        return False
    candle = df.iloc[-1]
    body   = abs(float(candle["close"]) - float(candle["open"]))
    return body > float(candle["atr"]) * MARKET_STRUCTURE[symbol_key]["displacement_mult"]

# ============================================================
# BOS
# ============================================================
def break_of_structure(df, direction):
    if len(df) < 10:
        return False
    atr   = float(df.iloc[-1]["atr"])
    close = float(df.iloc[-1]["close"])
    if direction == "BUY":
        return close > float(df["high"].iloc[-10:-1].max()) + atr * 0.10
    if direction == "SELL":
        return close < float(df["low"].iloc[-10:-1].min())  - atr * 0.10
    return False

# ============================================================
# VOLUME
# ============================================================
def institutional_volume(df):
    if len(df) < 21:
        return False
    last  = df.iloc[-1]
    vol   = float(last["volume"])
    volma = float(last["volma"]) if not pd.isna(last["volma"]) else 0
    return volma > 0 and vol > volma * 1.8

def strong_candle(df, direction):
    if len(df) < 2:
        return False
    candle      = df.iloc[-1]
    open_p      = float(candle["open"]);  close_p = float(candle["close"])
    high_p      = float(candle["high"]);  low_p   = float(candle["low"])
    body        = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0 or body / total_range < 0.60:
        return False
    if direction == "BUY":  return close_p > (low_p + total_range * 0.70)
    if direction == "SELL": return close_p < (low_p + total_range * 0.30)
    return False

# ============================================================
# SUPPLY DEMAND ZONES
# ============================================================
def detect_supply_demand_zones(df):
    if len(df) < 20:
        return None, None
    recent = df.tail(20)
    return (
        recent["low"].rolling(5).min().iloc[-1],
        recent["high"].rolling(5).max().iloc[-1],
    )

# ============================================================
# MICRO BOS
# ============================================================
def micro_bos(df, direction):
    if len(df) < 4:
        return False
    if direction == "BUY":
        return float(df.iloc[-1]["close"]) > float(df.iloc[-2]["high"])
    if direction == "SELL":
        return float(df.iloc[-1]["close"]) < float(df.iloc[-2]["low"])
    return False

# ============================================================
# WAVETREND
# ============================================================
def wavetrend_confirmation(df, direction):
    if len(df) < 5:
        return False
    wt1_now  = float(df.iloc[-1]["wt1"]); wt2_now  = float(df.iloc[-1]["wt2"])
    wt1_prev = float(df.iloc[-2]["wt1"]); wt2_prev = float(df.iloc[-2]["wt2"])
    if direction == "BUY":
        return wt1_prev < wt2_prev and wt1_now > wt2_now and wt1_now < 20
    if direction == "SELL":
        return wt1_prev > wt2_prev and wt1_now < wt2_now and wt1_now > -20
    return False

# ============================================================
# HTF TREND
# ============================================================
def get_trend(symbol_key):
    cache = _htf_cache[symbol_key]
    now   = time.time()
    if now - cache["ts"] < HTF_REFRESH:
        return cache["trend"]
    df, _ = get_entry_data(symbol_key)
    if df is None:
        return "NEUTRAL"
    df = add_ind(df)
    if df is None or len(df) < 50:
        return "NEUTRAL"
    last = df.iloc[-1]
    if   last["ema21"] > last["ema50"]: trend = "BULL"
    elif last["ema21"] < last["ema50"]: trend = "BEAR"
    else: trend = MARKETS[symbol_key].get("bias", "NEUTRAL")
    cache["trend"] = trend
    cache["ts"]    = now
    return trend

# ============================================================
# WEEKLY / DAILY / H12 / H4 TREND
# ============================================================
def weekly_trend(df, direction):
    if df is None or len(df) < 260: return False
    ma = df["close"].rolling(250).mean().iloc[-1]
    price = float(df.iloc[-1]["close"])
    if pd.isna(ma): return False
    return price > ma if direction == "BUY" else price < ma

def daily_trend(df, direction):
    if df is None or len(df) < 210: return False
    price = float(df.iloc[-1]["close"]); ema200 = float(df.iloc[-1]["ema200"])
    return price > ema200 if direction == "BUY" else price < ema200

def h12_trend(df, direction):
    if df is None or len(df) < 150: return False
    ma = df["close"].rolling(144).mean().iloc[-1]
    price = float(df.iloc[-1]["close"])
    if pd.isna(ma): return False
    return price > ma if direction == "BUY" else price < ma

def h4_trend(df, direction):
    if df is None or len(df) < 55: return False
    price = float(df.iloc[-1]["close"]); ema50 = float(df.iloc[-1]["ema50"])
    return price > ema50 if direction == "BUY" else price < ema50

def quantum_macro_filter(df, direction):
    if df is None: return False
    score = 0
    if weekly_trend(df, direction): score += 3
    if daily_trend(df, direction):  score += 3
    if h12_trend(df, direction):    score += 2
    if h4_trend(df, direction):     score += 2
    return score >= 7

def mtf_bullish(symbol_key, df):
    if df is None or len(df) < 200: return False
    last = df.iloc[-1]
    return (float(last["ema9"]) > float(last["ema21"])
            and float(last["ema21"]) > float(last["ema50"])
            and float(last["close"]) > float(last["ema200"]))

def mtf_bearish(symbol_key, df):
    if df is None or len(df) < 200: return False
    last = df.iloc[-1]
    return (float(last["ema9"]) < float(last["ema21"])
            and float(last["ema21"]) < float(last["ema50"])
            and float(last["close"]) < float(last["ema200"]))

# ============================================================
# DETECT MARKET REGIME
# ============================================================
def detect_market_regime(df):
    adx = float(df.iloc[-1]["adx"])
    if adx >= 35:   return "BREAKOUT"
    elif adx >= 25: return "TREND"
    else:           return "RANGE"

# ============================================================
# ICT MASTER SIGNAL ENGINE
# ============================================================
def ict_signal_engine(df, symbol_key, session):
    if len(df) < 50:
        return None, 0, {}

    last  = df.iloc[-1]
    atr   = float(last["atr"])
    price = float(last["close"])
    rsi   = float(last["rsi"])

    mtf_trends  = ict_mtf_trend(df)
    smart_trend = smart_ai_short_term_trend(df)

    bull_mss,  bear_mss                     = detect_mss(df, symbol_key)
    bull_fvg,  bear_fvg, fvg_high, fvg_low  = detect_fvg(df, symbol_key)
    bull_ob,   bear_ob,  ob_high,  ob_low   = detect_order_block(df, symbol_key)
    bull_sweep, bear_sweep                   = detect_liquidity_sweep(df, symbol_key)
    bull_wick,  bear_wick                    = detect_wick_rejection(df, atr, symbol_key)
    pd_zone                                  = premium_discount(df, symbol_key)
    bos_buy    = break_of_structure(df, "BUY")
    bos_sell   = break_of_structure(df, "SELL")
    micro_buy  = micro_bos(df, "BUY")
    micro_sell = micro_bos(df, "SELL")
    strong_buy = elite_strong_candle(df, "BUY")
    strong_sell= elite_strong_candle(df, "SELL")
    wt_buy     = wavetrend_confirmation(df, "BUY")
    wt_sell    = wavetrend_confirmation(df, "SELL")
    inst_vol   = institutional_volume(df)
    demand_zone, supply_zone = detect_supply_demand_zones(df)

    buy_cond  = {}; buy_score  = 0
    sell_cond = {}; sell_score = 0

    tf_score_buy = ict_trend_score(mtf_trends, "BUY")
    if tf_score_buy >= 3:
        buy_score += tf_score_buy * 2
        buy_cond[f"MTF_ALIGNED_{tf_score_buy}/4"] = True

    if smart_trend == "BULLISH":    buy_score += 4; buy_cond["SMART_AI_BULLISH"]    = True
    if bull_mss:                    buy_score += 6; buy_cond["MSS_BULLISH"]          = True
    if bull_fvg:                    buy_score += 5; buy_cond["FVG_BULLISH"]          = True
    if bull_ob:                     buy_score += 5; buy_cond["ORDER_BLOCK_BULL"]     = True
    if bull_sweep:                  buy_score += 4; buy_cond["LIQUIDITY_SWEEP"]      = True
    if bull_wick:                   buy_score += 3; buy_cond["WICK_REJECTION"]       = True
    if pd_zone["discount"]:         buy_score += 2; buy_cond["DISCOUNT_ZONE"]       = True
    if bos_buy:                     buy_score += 3; buy_cond["BOS_BULLISH"]          = True
    if micro_buy:                   buy_score += 3; buy_cond["MICRO_BOS"]            = True
    if strong_buy:                  buy_score += 3; buy_cond["STRONG_CANDLE"]        = True
    if wt_buy:                      buy_score += 2; buy_cond["WAVETREND_BUY"]        = True
    if rsi <= 38:                   buy_score += 2; buy_cond["RSI_OVERSOLD"]         = True
    if inst_vol:                    buy_score += 2; buy_cond["INST_VOLUME"]          = True
    if demand_zone and price <= float(demand_zone) * 1.001:
                                    buy_score += 3; buy_cond["DEMAND_ZONE"]          = True
    if bull_mss and bull_fvg:       buy_score += 5; buy_cond["ICT_MSS+FVG_CLUSTER"] = True
    if bull_mss and bull_ob:        buy_score += 5; buy_cond["ICT_MSS+OB_CLUSTER"]  = True
    if bull_sweep and bull_fvg:     buy_score += 3; buy_cond["SWEEP+FVG_CLUSTER"]   = True

    tf_score_sell = ict_trend_score(mtf_trends, "SELL")
    if tf_score_sell >= 3:
        sell_score += tf_score_sell * 2
        sell_cond[f"MTF_ALIGNED_{tf_score_sell}/4"] = True

    if smart_trend == "BEARISH":    sell_score += 4; sell_cond["SMART_AI_BEARISH"]   = True
    if bear_mss:                    sell_score += 6; sell_cond["MSS_BEARISH"]         = True
    if bear_fvg:                    sell_score += 5; sell_cond["FVG_BEARISH"]         = True
    if bear_ob:                     sell_score += 5; sell_cond["ORDER_BLOCK_BEAR"]    = True
    if bear_sweep:                  sell_score += 4; sell_cond["LIQUIDITY_SWEEP"]     = True
    if bear_wick:                   sell_score += 3; sell_cond["WICK_REJECTION"]      = True
    if pd_zone["premium"]:          sell_score += 2; sell_cond["PREMIUM_ZONE"]       = True
    if bos_sell:                    sell_score += 3; sell_cond["BOS_BEARISH"]         = True
    if micro_sell:                  sell_score += 3; sell_cond["MICRO_BOS"]           = True
    if strong_sell:                 sell_score += 3; sell_cond["STRONG_CANDLE"]       = True
    if wt_sell:                     sell_score += 2; sell_cond["WAVETREND_SELL"]      = True
    if rsi >= 62:                   sell_score += 2; sell_cond["RSI_OVERBOUGHT"]      = True
    if inst_vol:                    sell_score += 2; sell_cond["INST_VOLUME"]         = True
    if supply_zone and price >= float(supply_zone) * 0.999:
                                    sell_score += 3; sell_cond["SUPPLY_ZONE"]         = True
    if bear_mss and bear_fvg:       sell_score += 5; sell_cond["ICT_MSS+FVG_CLUSTER"]= True
    if bear_mss and bear_ob:        sell_score += 5; sell_cond["ICT_MSS+OB_CLUSTER"] = True
    if bear_sweep and bear_fvg:     sell_score += 3; sell_cond["SWEEP+FVG_CLUSTER"]  = True

    buy_ict_valid  = bull_mss or (bull_fvg and bull_ob) or (bull_sweep and bull_fvg)
    sell_ict_valid = bear_mss or (bear_fvg and bear_ob) or (bear_sweep and bear_fvg)

    if not buy_ict_valid:  buy_score  = 0; buy_cond  = {}
    if not sell_ict_valid: sell_score = 0; sell_cond = {}

    if buy_score == 0 and sell_score == 0:
        return None, 0, {}

    if buy_score >= sell_score:
        return "BUY",  buy_score,  buy_cond
    else:
        return "SELL", sell_score, sell_cond

# ============================================================
# CONTINUATION RETEST ENGINE
# ============================================================
def detect_continuation_retest(df, symbol_key):
    if len(df) < 50:
        return None, 0, {}

    last  = df.iloc[-1]
    rsi   = float(last["rsi"])
    adx   = float(last["adx"])

    bull_fvg, bear_fvg, _, _ = detect_fvg(df, symbol_key)
    bull_ob,  bear_ob,  _, _ = detect_order_block(df, symbol_key)
    strong_buy  = elite_strong_candle(df, "BUY")
    strong_sell = elite_strong_candle(df, "SELL")
    mtf_trends  = ict_mtf_trend(df)

    buy_score = 0
    buy_cond  = {}

    if ict_trend_aligned(mtf_trends, "BUY"):
        if bull_fvg:   buy_score += 4; buy_cond["FVG_RETEST"]       = True
        if bull_ob:    buy_score += 3; buy_cond["OB_RETEST"]         = True
        if rsi > 50:   buy_score += 2; buy_cond["RSI_BULLISH"]       = True
        if adx > 22:   buy_score += 2; buy_cond["ADX_STRENGTH"]      = True
        if strong_buy: buy_score += 3; buy_cond["REJECTION_CANDLE"]  = True

    sell_score = 0
    sell_cond  = {}

    if ict_trend_aligned(mtf_trends, "SELL"):
        if bear_fvg:    sell_score += 4; sell_cond["FVG_RETEST"]      = True
        if bear_ob:     sell_score += 3; sell_cond["OB_RETEST"]        = True
        if rsi < 50:    sell_score += 2; sell_cond["RSI_BEARISH"]      = True
        if adx > 22:    sell_score += 2; sell_cond["ADX_STRENGTH"]     = True
        if strong_sell: sell_score += 3; sell_cond["REJECTION_CANDLE"] = True

    if buy_score >= 12 and buy_score > sell_score:
        return "BUY",  buy_score, buy_cond
    if sell_score >= 10 and sell_score > buy_score:
        return "SELL", sell_score, sell_cond

    return None, 0, {}

# ============================================================
# BTC AGGRESSIVE REVERSAL (BUY)
# ============================================================
def btc_aggressive_reversal(df, symbol_key):
    if symbol_key != "BTC/USD" or len(df) < 50:
        return None, 0, {}

    last   = df.iloc[-1]
    atr    = float(last["atr"])
    rsi    = float(last["rsi"])
    volume = float(last["volume"])
    volma  = float(last["volma"]) if not pd.isna(last["volma"]) else 0

    buy_score = 0
    buy_cond  = {}

    bull_sweep, _ = detect_liquidity_sweep(df, symbol_key)
    bull_wick, _  = detect_wick_rejection(df, atr, symbol_key)
    pd_zone       = premium_discount(df, symbol_key)
    strong_buy    = elite_strong_candle(df, "BUY")
    micro_buy     = micro_bos(df, "BUY")
    wt_buy        = wavetrend_confirmation(df, "BUY")

    if bull_sweep:                             buy_score += 4; buy_cond["BTC_LIQUIDITY_SWEEP"]        = True
    if pd_zone["discount"]:                    buy_score += 3; buy_cond["BTC_DISCOUNT_ZONE"]          = True
    if strong_buy:                             buy_score += 4; buy_cond["BTC_BULLISH_ENGULF"]         = True
    if bull_wick:                              buy_score += 3; buy_cond["BTC_WICK_REJECTION"]         = True
    if volma > 0 and volume > volma * 1.5:     buy_score += 4; buy_cond["BTC_VOLUME_SPIKE"]          = True
    if micro_buy:                              buy_score += 2; buy_cond["BTC_MICRO_BOS"]              = True
    if wt_buy:                                 buy_score += 2; buy_cond["BTC_WAVETREND"]              = True
    if rsi < 42:                               buy_score += 2; buy_cond["BTC_RSI_RECOVERY"]          = True
    if bull_sweep and strong_buy:              buy_score += 3; buy_cond["BTC_SWEEP+ENGULF_CLUSTER"]   = True
    if bull_sweep and pd_zone["discount"]:     buy_score += 3; buy_cond["BTC_SWEEP+DISCOUNT_CLUSTER"] = True
    if bull_sweep and volma > 0 and volume > volma * 1.5:
                                               buy_score += 3; buy_cond["BTC_SWEEP+VOLUME_CLUSTER"]   = True

    if (
        bull_sweep
        and pd_zone["discount"]
        and strong_buy
        and volma > 0
        and volume > volma * 1.5
        and buy_score >= BTC_REVERSAL_MIN_SCORE
    ):
        return "BUY", buy_score, buy_cond

    return None, 0, {}

# ============================================================
# BTC BEARISH BREAKDOWN (SELL)
# ============================================================
def btc_bearish_breakdown(df, symbol_key):
    if symbol_key != "BTC/USD" or len(df) < 50:
        return None, 0, {}

    last   = df.iloc[-1]
    rsi    = float(last["rsi"])
    adx    = float(last["adx"])
    atr    = float(last["atr"])
    volume = float(last["volume"])
    volma  = float(last["volma"]) if not pd.isna(last["volma"]) else 0

    sell_score = 0
    sell_cond  = {}

    _, bear_fvg, _, _ = detect_fvg(df, symbol_key)
    _, bear_ob, _, _  = detect_order_block(df, symbol_key)
    _, bear_sweep     = detect_liquidity_sweep(df, symbol_key)
    _, bear_wick      = detect_wick_rejection(df, atr, symbol_key)
    bos_sell          = break_of_structure(df, "SELL")
    micro_sell        = micro_bos(df, "SELL")
    strong_sell       = elite_strong_candle(df, "SELL")
    wt_sell           = wavetrend_confirmation(df, "SELL")
    pd_zone           = premium_discount(df, symbol_key)

    if bear_fvg:                               sell_score += 4; sell_cond["BTC_BEAR_FVG"]           = True
    if bear_ob:                                sell_score += 4; sell_cond["BTC_BEAR_OB"]            = True
    if bear_sweep:                             sell_score += 3; sell_cond["BTC_LIQUIDITY_SWEEP"]     = True
    if bear_wick:                              sell_score += 3; sell_cond["BTC_WICK_REJECTION"]      = True
    if bos_sell:                               sell_score += 4; sell_cond["BTC_BOS_SELL"]           = True
    if micro_sell:                             sell_score += 2; sell_cond["BTC_MICRO_BOS"]          = True
    if strong_sell:                            sell_score += 4; sell_cond["BTC_STRONG_SELL_CANDLE"]  = True
    if wt_sell:                                sell_score += 2; sell_cond["BTC_WAVETREND_SELL"]     = True
    if pd_zone["premium"]:                     sell_score += 3; sell_cond["BTC_PREMIUM_ZONE"]       = True
    if rsi < 45:                               sell_score += 2; sell_cond["BTC_RSI_BEARISH"]        = True
    if adx > 20:                               sell_score += 2; sell_cond["BTC_ADX_STRENGTH"]       = True
    if volma > 0 and volume > volma * 1.4:     sell_score += 4; sell_cond["BTC_VOLUME_SPIKE"]       = True
    if bear_fvg and bear_ob:                   sell_score += 4; sell_cond["BTC_OB+FVG_CLUSTER"]     = True
    if bos_sell and strong_sell:               sell_score += 4; sell_cond["BTC_BOS+DISPLACEMENT"]   = True
    if bear_sweep and bear_fvg:                sell_score += 3; sell_cond["BTC_SWEEP+FVG_CLUSTER"]  = True
    if bear_ob and pd_zone["premium"]:         sell_score += 3; sell_cond["BTC_OB+PREMIUM_CLUSTER"] = True

    if (
        sell_score >= BTC_BREAKDOWN_MIN_SCORE
        and (bear_fvg or bear_ob or bos_sell)
        and strong_sell
    ):
        return "SELL", sell_score, sell_cond

    return None, 0, {}

# ============================================================
# INSTITUTIONAL STRUCTURE SCORE
# ============================================================
def institutional_structure_score(df, symbol_key):
    bull_sweep, bear_sweep = detect_liquidity_sweep(df, symbol_key)
    bull_wick,  bear_wick  = detect_wick_rejection(df, float(df.iloc[-1]["atr"]), symbol_key)
    displacement           = detect_displacement(df, symbol_key)
    pd_zone                = premium_discount(df, symbol_key)
    buy_score = sell_score = 0
    buy_cond  = {}; sell_cond = {}
    if bull_sweep: buy_score  += 2; buy_cond["SWEEP"]        = True
    if bull_wick:  buy_score  += 2; buy_cond["WICK"]         = True
    if detect_zone_retest(df, symbol_key, "BUY"):
                   buy_score  += 2; buy_cond["ZONE"]         = True
    if displacement: buy_score += 2; buy_cond["DISPLACEMENT"] = True
    if pd_zone["discount"]: buy_score += 1; buy_cond["DISCOUNT"] = True
    if bear_sweep: sell_score += 2; sell_cond["SWEEP"]        = True
    if bear_wick:  sell_score += 2; sell_cond["WICK"]         = True
    if detect_zone_retest(df, symbol_key, "SELL"):
                   sell_score += 2; sell_cond["ZONE"]         = True
    if displacement: sell_score += 2; sell_cond["DISPLACEMENT"] = True
    if pd_zone["premium"]: sell_score += 1; sell_cond["PREMIUM"] = True
    if buy_score  >= 8: buy_score  += 1
    if sell_score >= 8: sell_score += 1
    return buy_cond, sell_cond, buy_score, sell_score

# ============================================================
# WIZARD AI
# ============================================================
def wizard_ai_confirmation(df, symbol_key, direction):
    if len(df) < 250:
        return False, 0
    last   = df.iloc[-1]
    close  = float(last["close"]); ema50  = float(last["ema50"])
    ema200 = float(last["ema200"]); rsi   = float(last["rsi"])
    adx    = float(last["adx"]);   volume = float(last["volume"])
    volma  = float(last["volma"]) if not pd.isna(last["volma"]) else 0
    aox    = float(last["aox"])   if not pd.isna(last["aox"])   else 0
    score  = 0
    if direction == "BUY":
        if close > ema50:                 score += 3
        if ema50  > ema200:               score += 3
        if rsi    > 55:                   score += 2
        if adx    > WIZARD_ADX_THRESHOLD: score += 2
        if aox    > 0:                    score += 2
    elif direction == "SELL":
        if close < ema50:                 score += 3
        if ema50  < ema200:               score += 3
        if rsi    < 45:                   score += 2
        if adx    > WIZARD_ADX_THRESHOLD: score += 2
        if aox    < 0:                    score += 2
    if volma > 0 and volume > volma * WIZARD_VOLUME_MULT:
        score += 3
    bull_fvg, bear_fvg, _, _ = detect_fvg(df, symbol_key)
    bull_sweep, bear_sweep   = detect_liquidity_sweep(df, symbol_key)
    bull_wick, bear_wick     = detect_wick_rejection(df, float(last["atr"]), symbol_key)
    bull_mss, bear_mss       = detect_mss(df, symbol_key)
    if direction == "BUY":
        if bull_fvg:   score += 3
        if bull_mss:   score += 4
        if bull_sweep: score += 2
        if bull_wick:  score += 2
    elif direction == "SELL":
        if bear_fvg:   score += 3
        if bear_mss:   score += 4
        if bear_sweep: score += 2
        if bear_wick:  score += 2
    pd_zone = premium_discount(df, symbol_key)
    if direction == "BUY"  and pd_zone["discount"]: score += 2
    if direction == "SELL" and pd_zone["premium"]:  score += 2
    return score >= WIZARD_MIN_SCORE, score

# ============================================================
# ULTRA SNIPER SCORE
# ============================================================
def ultra_sniper_score(df, symbol_key, direction):
    score = 0
    last  = df.iloc[-1]
    rsi   = float(last["rsi"]); adx = float(last["adx"])
    vol   = float(last["volume"])
    volma = float(last["volma"]) if not pd.isna(last["volma"]) else 0
    bull_sweep, bear_sweep   = detect_liquidity_sweep(df, symbol_key)
    bull_fvg, bear_fvg, _, _ = detect_fvg(df, symbol_key)
    bull_mss, bear_mss       = detect_mss(df, symbol_key)
    if direction == "BUY"  and mtf_bullish(symbol_key, df): score += 6
    if direction == "SELL" and mtf_bearish(symbol_key, df): score += 6
    if wavetrend_confirmation(df, direction): score += 3
    if direction == "BUY":
        if bull_sweep: score += 3
        if bull_fvg:   score += 3
        if bull_mss:   score += 5
    if direction == "SELL":
        if bear_sweep: score += 3
        if bear_fvg:   score += 3
        if bear_mss:   score += 5
    if break_of_structure(df, direction): score += 3
    if institutional_volume(df):          score += 2
    if strong_candle(df, direction):      score += 2
    if direction == "BUY"  and rsi > 60: score += 3
    if direction == "SELL" and rsi < 40: score += 3
    if adx > 30:  score += 3
    if volma > 0 and vol > volma * 1.7: score += 4
    return score

# ============================================================
# HELPERS
# ============================================================
def determine_best_direction(buy_score, sell_score):
    return "BUY" if buy_score >= sell_score else "SELL"

def trade_quality(score):
    if   score >= 40: return "BLACKROCK-TIER"
    elif score >= 32: return "GOD-TIER"
    elif score >= 26: return "ELITE"
    elif score >= 20: return "HIGH-PROBABILITY"
    return "STANDARD"

def adaptive_risk(session):
    if   session == "London":      return 1.2
    elif session == "NY Killzone": return 1.4
    return 1.1

def get_dynamic_rr(symbol_key, regime):
    return RR_PROFILE.get(symbol_key, {}).get(regime, MARKETS[symbol_key]["rr"])

def get_signal_number(symbol_key, session):
    global _signal_counter
    if _signal_counter[symbol_key]["session"] != session:
        _signal_counter[symbol_key]["session"] = session
        _signal_counter[symbol_key]["count"]   = 1
    else:
        _signal_counter[symbol_key]["count"] += 1
    n = _signal_counter[symbol_key]["count"]
    entry_type = (
        "PRIMARY ICT ENTRY"     if n == 1 else
        "SECONDARY RETEST"      if n == 2 else
        "ADVANCED CONTINUATION"
    )
    return n, entry_type

# ============================================================
# SESSION FILTER
# ============================================================
def in_session(symbol_key):
    h = datetime.now(timezone.utc).hour

    if symbol_key == "BTC/USD":
        return True, "24H"

    if 8 <= h < 11:
        return True, "London"
    if 13 <= h < 15:
        return True, "NY Killzone"
    if 14 <= h < 16:
        return True, "NY+London"

    return False, "Closed"
# ============================================================
# SPREAD / VOLATILITY
# ============================================================
def spread_too_high(symbol_key, spread):
    return spread > MAX_SPREAD[symbol_key] * 0.90

def volatility_danger(df, symbol_key):
    if len(df) < 60: return False
    atr     = float(df.iloc[-1]["atr"])
    atr_avg = df["atr"].rolling(50).mean().iloc[-1]
    if pd.isna(atr_avg) or atr_avg == 0: return False
    return (atr / atr_avg) > 2.0

def quantum_volatility_ok(df):
    if len(df) < 60: return False
    atr     = float(df.iloc[-1]["atr"])
    atr_avg = df["atr"].rolling(50).mean().iloc[-1]
    if pd.isna(atr_avg) or atr_avg == 0: return False
    return 0.75 <= (atr / atr_avg) <= 2.10

def false_breakout_filter(df, direction):
    if len(df) < 3: return False
    last = df.iloc[-1]; prev = df.iloc[-2]
    atr  = float(df.iloc[-1]["atr"])
    if direction == "BUY":
        return float(last["close"]) > float(prev["high"]) - atr * 0.05
    if direction == "SELL":
        return float(last["close"]) < float(prev["low"])  + atr * 0.05
    return False

# ============================================================
# CORRELATION BLOCKER
# ============================================================
def correlated_signal_block(symbol_key):
    if not CORRELATION_BLOCK: return False
    for group in CORRELATED_GROUPS:
        if symbol_key in group:
            active = sum(
                1 for s in group
                if time.time() - _signal_sent.get(s, 0) < 7200
            )
            if active >= MAX_OPEN_CORRELATED:
                log.info(f"Correlation blocker active for {symbol_key}")
                return True
    return False

# ============================================================
# DUPLICATE SIGNAL FILTER
# ============================================================
def duplicate_signal(symbol_key, direction):
    now = time.time()
    duplicate_windows = {
        "XAU/USD": 3600, "NAS100": 5400, "EUR/USD": 3600,
        "GBP/JPY": 3600, "BTC/USD": 1800,
    }
    cooldown = duplicate_windows.get(symbol_key, 3600)
    with signal_lock:
        last_dir  = _last_signal_direction.get(symbol_key)
        last_time = _last_signal_time.get(symbol_key, 0)
        if last_dir == direction and now - last_time < cooldown:
            remaining = int(cooldown - (now - last_time))
            log.info(f"Duplicate blocked {symbol_key} ({remaining}s remaining)")
            return True
        _last_signal_direction[symbol_key] = direction
        _last_signal_time[symbol_key]      = now
    return False

def economic_news_block():
    return False

# ============================================================
# SMART TP TARGET
# ============================================================
def smart_tp_target(df, symbol_key, direction, entry, sl):
    atr      = float(df.iloc[-1]["atr"])
    rr_floor = 1.8
    recent   = df.tail(80)
    demand_zone, supply_zone = detect_supply_demand_zones(df)

    if direction == "BUY":
        candidates = []
        highs = recent["high"][recent["high"] > entry].sort_values().unique()
        for h in highs:
            candidates.append(float(h))
        if supply_zone and supply_zone > entry:
            candidates.append(float(supply_zone))
        eq_high = recent["high"].rolling(3).max().max()
        if eq_high > entry:
            candidates.append(float(eq_high))
        tp = min(candidates) if candidates else entry + max(
            (entry - sl) * rr_floor, atr * 2.5
        )
    else:
        candidates = []
        lows = recent["low"][recent["low"] < entry].sort_values(ascending=False).unique()
        for l in lows:
            candidates.append(float(l))
        if demand_zone and demand_zone < entry:
            candidates.append(float(demand_zone))
        eq_low = recent["low"].rolling(3).min().min()
        if eq_low < entry:
            candidates.append(float(eq_low))
        tp = max(candidates) if candidates else entry - max(
            (sl - entry) * rr_floor, atr * 2.5
        )

    return round(tp, MARKETS[symbol_key]["decimals"])

# ============================================================
# ICT SL PLACEMENT + SMART TP
# ============================================================
def ict_calc_levels(price, atr, symbol_key, df, direction, rr):
    min_sl   = MARKETS[symbol_key]["min_sl"]
    decimals = MARKETS[symbol_key]["decimals"]

    bull_ob, bear_ob, ob_high, ob_low      = detect_order_block(df, symbol_key)
    bull_fvg, bear_fvg, fvg_high, fvg_low = detect_fvg(df, symbol_key)

    if direction == "BUY":
        sl_refs = []
        if bull_ob  and ob_low  is not None: sl_refs.append(ob_low  - atr * 0.15)
        if bull_fvg and fvg_low is not None: sl_refs.append(fvg_low - atr * 0.10)
        sl_refs.append(float(df.tail(10)["low"].min()) - atr * 0.10)
        sl      = min(sl_refs) if sl_refs else price - atr * ATR_MULT * ATR_MARKET_MULTIPLIER[symbol_key]
        sl_dist = price - sl
        if sl_dist < min_sl:
            sl = price - min_sl; sl_dist = min_sl
        tp = smart_tp_target(df, symbol_key, direction, price, sl)
        rr = round(abs(tp - price) / abs(price - sl), 2)
    else:
        sl_refs = []
        if bear_ob  and ob_high  is not None: sl_refs.append(ob_high  + atr * 0.15)
        if bear_fvg and fvg_high is not None: sl_refs.append(fvg_high + atr * 0.10)
        sl_refs.append(float(df.tail(10)["high"].max()) + atr * 0.10)
        sl      = max(sl_refs) if sl_refs else price + atr * ATR_MULT * ATR_MARKET_MULTIPLIER[symbol_key]
        sl_dist = sl - price
        if sl_dist < min_sl:
            sl = price + min_sl; sl_dist = min_sl
        tp = smart_tp_target(df, symbol_key, direction, price, sl)
        rr = round(abs(tp - price) / abs(price - sl), 2)

    return round(sl, decimals), round(tp, decimals), round(sl_dist, decimals), rr

# ============================================================
# LOT SIZE
# ============================================================
def lot_for_risk(price, sl, symbol_key, risk_multiplier=1.0):
    base_risk = 50
    risk      = base_risk * risk_multiplier
    sl_dist   = abs(price - sl)
    if sl_dist <= 0: return 0.01
    lot  = risk / (sl_dist * DOLLAR_PER_POINT[symbol_key])
    caps = {
        "XAU/USD": 1.50, "NAS100": 2.00, "EUR/USD": 3.00,
        "GBP/JPY": 2.00, "BTC/USD": 0.10,
    }
    return round(max(0.01, min(lot, caps[symbol_key])), 3)

# ============================================================
# EXECUTE TRADE
# ============================================================
def execute_trade(symbol_key, df, direction, best, wizard_score,
                  sniper_score, macro_trend, session, trend,
                  regime, conditions, source, rr, mtf_trends):

    price = float(df.iloc[-1]["close"])
    atr   = float(df.iloc[-1]["atr"])
    rsi   = float(df.iloc[-1]["rsi"])
    adx   = float(df.iloc[-1]["adx"])
    dec   = MARKETS[symbol_key]["decimals"]

    if direction == "BUY":
        price += EXECUTION_BUFFER[symbol_key]
    else:
        price -= EXECUTION_BUFFER[symbol_key]

    sl, tp, sl_dist, rr = ict_calc_levels(price, atr, symbol_key, df, direction, rr)

    risk_mult      = adaptive_risk(session)
    lot            = lot_for_risk(price, sl, symbol_key, risk_mult)
    quality        = trade_quality(best)
    timeframe      = REGIME_TIMEFRAME.get(regime, "1H / 4H")
    signal_num, entry_type = get_signal_number(symbol_key, session)
    signal_type    = "ICT_SNIPER"

    log_signal(symbol_key, direction, best, rr, price, sl, tp,
               session, regime, timeframe, signal_type)
    sync_real_pnl()

    cond_text    = "\n".join([f"✅ {k}" for k, v in conditions.items() if v])
    action_emoji = "📈" if direction == "BUY" else "📉"
    priority_tag = "🔱 *PRIORITY MARKET*\n" if symbol_key in PRIORITY_MARKETS else ""
    mtf_str      = " | ".join([f"{tf}: {tr[:4]}" for tf, tr in mtf_trends.items()])

    tp1 = (
        round(price + (tp - price) * 0.5, dec)
        if direction == "BUY"
        else round(price - (price - tp) * 0.5, dec)
    )

    msg = (
        f"🎯 *{SYSTEM_VERSION}* | ICT SNIPER\n"
        f"*{MARKETS[symbol_key]['mt5']}* | "
        f"⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n"
        f"{priority_tag}\n"
        f"🔥 *Action:* {direction} {action_emoji}\n"
        f"🎯 *Signal #:* {signal_num}\n"
        f"📍 *Entry Type:* {entry_type}\n"
        f"🚀 *Signal Type:* {signal_type}\n"
        f"⭐ *Total Score:* {best}\n"
        f"🏆 *Trade Quality:* {quality}\n"
        f"🌍 *Macro Trend:* {macro_trend}\n"
        f"🧠 *MTF Trend:* {mtf_str}\n"
        f"🎯 *Sniper Score:* {sniper_score}\n"
        f"🧠 *Wizard AI Score:* {wizard_score if ENABLE_WIZARD_AI else 'OFF'}\n"
        f"🧠 *Regime:* {regime}\n"
        f"⏱ *Timeframe:* {timeframe}\n"
        f"📊 *Market Bias:* {MARKETS[symbol_key]['bias']}\n\n"
        f"📍 *Entry:* {price:,.{dec}f}\n"
        f"🛑 *SL:* {sl:,.{dec}f}\n"
        f"🎯 *TP1 (1:1):* {tp1:,.{dec}f}\n"
        f"🎯 *Smart TP (1:{rr}):* {tp:,.{dec}f}\n"
        f"📊 *Actual RR:* 1:{rr}\n"
        f"🎯 *TP Model:* Previous Structure Liquidity Target\n\n"
        f"📈 *RSI:* {rsi:.1f}\n"
        f"📉 *ADX:* {adx:.1f}\n"
        f"🌍 *Trend:* {trend}\n"
        f"⏰ *Session:* {session}\n"
        f"🧠 *Mode:* ICT CONCEPT ENGINE\n"
        f"📡 *Source:* {source}\n\n"
        f"💵 *Lot:* {lot}\n\n"
        f"✅ *ICT Conditions:*\n"
        f"{cond_text}\n\n"
        f"🛡 *MSS + FVG + OB ENGINE ACTIVE*\n"
        f"⚡ *ULTIMATE ICT SUPREME — 2026 ELITE*"
    )

    send_telegram(msg)
    log.info(
        f"ICT SIGNAL {symbol_key} {direction} | "
        f"Entry: {price} | SL: {sl} | TP: {tp} | RR: {rr} | "
        f"Quality: {quality} | Score: {best} | Regime: {regime}"
    )

# ============================================================
# PROCESS SYMBOL
# ============================================================
def process_symbol(symbol_key):
    log.info(f"Scanning {symbol_key}")

    # ============================================================
    # DAILY SIGNAL CAP
    # ============================================================
    if _daily_signal_count[symbol_key] >= MAX_SIGNALS_PER_DAY[symbol_key]:
        log.info(f"REJECTED {symbol_key} daily cap reached")
        return

    # ============================================================
    # CIRCUIT BREAKERS
    # ============================================================
    if weekend_block(symbol_key):
        log.info(f"REJECTED {symbol_key} weekend block active")
        return

    if daily_loss_lock():
        log.info(f"REJECTED {symbol_key} daily loss lock active")
        return

    if loss_streak_lock():
        log.info(f"REJECTED {symbol_key} consecutive loss lock active")
        return

    watchdog()
    rotate_log()

    # ============================================================
    # SESSION FILTER
    # ============================================================
    ok, session = in_session(symbol_key)

    if not ok:
        log.info(f"REJECTED {symbol_key} outside active trading session")
        return

    if session not in ALLOWED_SESSIONS:
        log.info(f"REJECTED {symbol_key} session not allowed ({session})")
        return

    # ============================================================
    # ECONOMIC NEWS FILTER
    # ============================================================
    if economic_news_block():
        log.info(f"REJECTED {symbol_key} economic news block active")
        return

    # ============================================================
    # MARKET DATA FETCH
    # ============================================================
    df, source = get_entry_data(symbol_key)

    if df is None:
        log.info(f"REJECTED {symbol_key} no market data retrieved")
        return

    if len(df) < 100:
        log.info(f"REJECTED {symbol_key} insufficient raw market data ({len(df)} candles)")
        return

    # ============================================================
    # SPREAD FILTER
    # ============================================================
    spread = get_spread(df)

    if spread_too_high(symbol_key, spread):
        log.info(f"REJECTED {symbol_key} spread too high ({spread:.6f})")
        return

    # ============================================================
    # INDICATOR PROCESSING
    # ============================================================
    df = add_ind(df)

    if df is None:
        log.info(f"REJECTED {symbol_key} indicator processing failed")
        return

    if len(df) < 80:
        log.info(f"REJECTED {symbol_key} insufficient indicator data ({len(df)} candles)")
        return

    # ============================================================
    # VOLATILITY FILTER
    # ============================================================
    if volatility_danger(df, symbol_key):
        log.info(f"REJECTED {symbol_key} volatility danger")
        return

    price = float(df.iloc[-1]["close"])
    atr   = float(df.iloc[-1]["atr"])

    # ============================================================
    # PRICE VALIDATION
    # ============================================================
    if price <= 0:
        log.info(f"REJECTED {symbol_key} invalid price ({price})")
        return

    if not (MARKETS[symbol_key]["price_lo"] <= price <= MARKETS[symbol_key]["price_hi"]):
        log.info(f"REJECTED {symbol_key} price out of range ({price})")
        return

    # ============================================================
    # TREND / REGIME
    # ============================================================
    trend  = get_trend(symbol_key)
    regime = detect_market_regime(df)

    macro_trend = (
        "BULL"
        if weekly_trend(df, "BUY") and daily_trend(df, "BUY")
        else "BEAR"
        if weekly_trend(df, "SELL") and daily_trend(df, "SELL")
        else "NEUTRAL"
    )

    mtf_trends = ict_mtf_trend(df)

    # ============================================================
    # PRIMARY ICT SIGNAL ENGINE
    # ============================================================
    direction, ict_score, conditions = ict_signal_engine(df, symbol_key, session)

    # ============================================================
    # BTC AGGRESSIVE REVERSAL
    # ============================================================
    if (
        (direction is None or ict_score == 0)
        and symbol_key == "BTC/USD"
        and ENABLE_BTC_AGGRESSIVE_REVERSAL
    ):
        log.info(f"{symbol_key} primary ICT failed — checking BTC aggressive reversal")
        direction, ict_score, conditions = btc_aggressive_reversal(df, symbol_key)

    # ============================================================
    # BTC BEARISH BREAKDOWN
    # ============================================================
    if (
        (direction is None or ict_score == 0)
        and symbol_key == "BTC/USD"
        and ENABLE_BTC_BREAKDOWN_MODE
    ):
        log.info(f"{symbol_key} reversal failed — checking BTC bearish breakdown")
        direction, ict_score, conditions = btc_bearish_breakdown(df, symbol_key)

    # ============================================================
    # CONTINUATION RETEST FALLBACK
    # ============================================================
    if direction is None or ict_score == 0:
        log.info(f"{symbol_key} no primary setup — checking continuation retest")
        direction, ict_score, conditions = detect_continuation_retest(df, symbol_key)

    # ============================================================
    # FINAL SIGNAL FAILURE
    # ============================================================
    if direction is None or ict_score == 0:
        log.info(f"REJECTED {symbol_key} no valid ICT / BTC / continuation setup")
        return

    log.info(
        f"{symbol_key} SIGNAL DETECTED | "
        f"Direction: {direction} | "
        f"ICT Score: {ict_score} | "
        f"Regime: {regime} | "
        f"Session: {session}"
    )

    # ============================================================
    # MINIMUM SCORE FILTER
    # ============================================================
    if (
        "FVG_RETEST" in conditions
        or "OB_RETEST" in conditions
        or "BTC_LIQUIDITY_SWEEP" in conditions
        or "BTC_BEAR_FVG" in conditions
        or "BTC_BEAR_OB" in conditions
    ):
        min_ict = 10
    else:
        min_ict = SESSION_THRESHOLDS.get(session, 16)

    if ict_score < min_ict:
        log.info(
            f"REJECTED {symbol_key} ICT score below threshold "
            f"({ict_score} < {min_ict})"
        )
        return

    # ============================================================
    # VOLATILITY KILL SWITCH
    # ============================================================
    if VOLATILITY_KILL and not quantum_volatility_ok(df):
        log.info(f"REJECTED {symbol_key} volatility kill filter")
        return

    # ============================================================
    # FALSE BREAKOUT FILTER
    # ============================================================
    if (
        FALSE_BREAK_FILTER
        and regime in ["TREND", "BREAKOUT"]
        and symbol_key != "BTC/USD"
    ):
        if not false_breakout_filter(df, direction):
            log.info(f"REJECTED {symbol_key} false breakout filter")
            return

    # ============================================================
    # WIZARD AI
    # ============================================================
    wizard_score = 0

    if ENABLE_WIZARD_AI:
        wizard_pass, wizard_score = wizard_ai_confirmation(df, symbol_key, direction)

        if symbol_key == "BTC/USD":
            if (
                "BTC_LIQUIDITY_SWEEP" in conditions
                or "BTC_BEAR_FVG"     in conditions
                or "BTC_BEAR_OB"      in conditions
                or "BTC_BOS_SELL"     in conditions
            ):
                wizard_pass = True
                log.info(f"{symbol_key} Wizard AI bypass activated")

        if not wizard_pass:
            log.info(f"REJECTED {symbol_key} Wizard AI failed (Score: {wizard_score})")
            return

        ict_score += int(wizard_score * 0.25)

    # ============================================================
    # ULTRA SNIPER SCORE
    # ============================================================
    sniper_score = ultra_sniper_score(df, symbol_key, direction)
    ict_score   += int(sniper_score * 0.30)

    # ============================================================
    # BTC SCORE BOOSTER
    # ============================================================
    if symbol_key == "BTC/USD":
        if "BTC_BEAR_FVG"        in conditions: ict_score += 2
        if "BTC_BEAR_OB"         in conditions: ict_score += 2
        if "BTC_BOS_SELL"        in conditions: ict_score += 2
        if "BTC_VOLUME_SPIKE"    in conditions: ict_score += 2
        if "BTC_LIQUIDITY_SWEEP" in conditions: ict_score += 2

    # ============================================================
    # COUNTERTREND FILTER
    # ============================================================
    if regime != "RANGE" and symbol_key not in ["XAU/USD", "BTC/USD"]:
        if trend == "BULL" and direction == "SELL":
            log.info(f"REJECTED {symbol_key} countertrend SELL blocked")
            return
        if trend == "BEAR" and direction == "BUY":
            log.info(f"REJECTED {symbol_key} countertrend BUY blocked")
            return

    # ============================================================
    # CORRELATION BLOCKER
    # ============================================================
    if correlated_signal_block(symbol_key):
        log.info(f"REJECTED {symbol_key} correlation blocker")
        return

    # ============================================================
    # DUPLICATE FILTER
    # ============================================================
    if duplicate_signal(symbol_key, direction):
        log.info(f"REJECTED {symbol_key} duplicate signal")
        return

    now = time.time()

    # ============================================================
    # COOLDOWN FILTER
    # ============================================================
    symbol_cooldown = 1800 if symbol_key == "BTC/USD" else SIGNAL_COOLDOWN

    if now - _signal_sent[symbol_key] < symbol_cooldown:
        remaining = int(symbol_cooldown - (now - _signal_sent[symbol_key]))
        log.info(f"REJECTED {symbol_key} cooldown active ({remaining}s remaining)")
        return

    # ============================================================
    # RR ENGINE
    # ============================================================
    if symbol_key == "BTC/USD":
        if "BTC_BEAR_FVG" in conditions or "BTC_BEAR_OB" in conditions:
            rr = BTC_BREAKDOWN_RR
        elif "BTC_LIQUIDITY_SWEEP" in conditions:
            rr = BTC_REVERSAL_RR
        else:
            rr = get_dynamic_rr(symbol_key, regime)
    else:
        rr = get_dynamic_rr(symbol_key, regime)

    # ============================================================
    # FINAL SIGNAL EXECUTION
    # ============================================================
    with signal_lock:
        _signal_sent[symbol_key]        = now
        _daily_signal_count[symbol_key] += 1

    log.info(
        f"EXECUTING {symbol_key} {direction} | "
        f"Final Score: {ict_score} | "
        f"Wizard: {wizard_score} | "
        f"Sniper: {sniper_score} | "
        f"RR: {rr}"
    )

    execute_trade(
        symbol_key, df, direction, ict_score, wizard_score,
        sniper_score, macro_trend, session, trend,
        regime, conditions, source, rr, mtf_trends,
    )

# ============================================================
# MAIN LOOP
# ============================================================
def main():
    log.info(f"{SYSTEM_VERSION} STARTED")
    send_telegram(
        f"🚀 *{SYSTEM_VERSION} LIVE*\n\n"
        f"📊 *Markets Active:*\n"
        f"🥇 XAU/USD\n📈 NAS100\n💶 EUR/USD\n💷 GBP/JPY\n₿ BTC/USD\n\n"
        f"🔱 All Markets Priority\n\n"
        f"🧠 *ICT ENGINE ACTIVE:*\n"
        f"✅ Market Structure Shift (MSS)\n"
        f"✅ Fair Value Gap (FVG)\n"
        f"✅ Order Block (OB)\n"
        f"✅ Liquidity Sweep\n"
        f"✅ MTF Trend 5M/1H/4H/12H\n"
        f"✅ Premium & Discount Zones\n"
        f"✅ ICT SL Placement (OB/FVG based)\n"
        f"✅ Smart TP — Structure Liquidity Target\n"
        f"✅ Dynamic RR (auto-calculated)\n"
        f"✅ Continuation Retest Engine\n"
        f"✅ BTC Aggressive Reversal Mode\n"
        f"✅ BTC Bearish Breakdown Mode\n"
        f"✅ BTC Score Booster\n"
        f"✅ BTC False Breakout Exempt\n"
        f"✅ BTC Countertrend Exempt\n"
        f"✅ BTC Wizard AI Bypass\n"
        f"✅ BTC Dynamic Cooldown\n"
        f"✅ Wizard AI Filter\n"
        f"✅ Ultra Sniper Score\n"
        f"✅ WaveTrend Confirmation\n"
        f"🔒 Correlation Blocker\n"
        f"🚫 False Breakout Filter\n"
        f"🧵 Thread Safe\n"
        f"⚡ ULTIMATE ICT SUPREME 2026 ELITE — LIVE"
    )

    while True:
        try:
            reset_daily()
            with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
                futures = []
                for symbol in PRIORITY_MARKETS:
                    futures.append(executor.submit(process_symbol, symbol))
                    time.sleep(0.35)
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        log.error(f"Thread error: {e}")
            gc.collect()
            time.sleep(MAIN_LOOP_DELAY)
        except Exception as e:
            log.error(f"Main loop error: {e}")
            time.sleep(MAIN_LOOP_DELAY)

if __name__ == "__main__":
    main()
