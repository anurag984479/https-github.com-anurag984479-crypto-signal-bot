# ============================================================
# PEPPERSTONE MOMENTUM HUNTER
# ULTIMATE-HYBRID-SUPREME
# XAU/USD + NAS100 + DE30 + US30
# MAXIMUM WINRATE ENGINE
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

SYSTEM_VERSION = "ULTIMATE-HYBRID-SUPREME"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("ULTIMATE-SUPREME")

TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

session_http = requests.Session()
signal_lock  = Lock()
log_lock     = Lock()

# ============================================================
# PRIORITY MARKETS
# ============================================================
PRIORITY_MARKETS = ["XAU/USD", "NAS100", "US30"]

# ============================================================
# SESSION SCORE THRESHOLDS
# ============================================================
SESSION_THRESHOLDS = {
    "Asian Precision": 22,
    "London":          18,
    "NY Killzone":     18,
    "NY+London":       17,
}

# ============================================================
# DYNAMIC RR PROFILES
# ============================================================
RR_PROFILE = {
    "XAU/USD": {"TREND": 3.2, "BREAKOUT": 3.8, "RANGE": 2.4},
    "NAS100":  {"TREND": 3.0, "BREAKOUT": 3.5, "RANGE": 2.3},
    "DE30":    {"TREND": 3.1, "BREAKOUT": 3.7, "RANGE": 2.4},
    "US30":    {"TREND": 2.9, "BREAKOUT": 3.4, "RANGE": 2.2},
}

# ============================================================
# MARKETS
# ============================================================
MARKETS = {
    "XAU/USD": {
        "mt5":         "XAUUSD.Qraw",
        "yf":          "GC=F",
        "price_lo":    4000,
        "price_hi":    7000,
        "sessions":    [0, 20],
        "decimals":    2,
        "min_sl":      7.0,
        "tier":        "GOLD ELITE",
        "bias":        "BULL",
        "rr":          2.8,
        "sweep_bonus": 3,
        "wick_ratio":  1.8,
    },
    "NAS100": {
        "mt5":         "NAS100",
        "yf":          "^NDX",
        "price_lo":    15000,
        "price_hi":    30000,
        "sessions":    [0, 21],
        "decimals":    1,
        "min_sl":      55.0,
        "tier":        "NASDAQ ELITE",
        "bias":        "BULL",
        "rr":          2.7,
        "sweep_bonus": 2,
        "wick_ratio":  1.6,
    },
    "DE30": {
        "mt5":         "DE30.Qraw",
        "yf":          "^GDAXI",
        "price_lo":    15000,
        "price_hi":    25000,
        "sessions":    [0, 18],
        "decimals":    1,
        "min_sl":      50.0,
        "tier":        "DE30 ELITE",
        "bias":        "BULL",
        "rr":          2.8,
        "sweep_bonus": 3,
        "wick_ratio":  1.7,
    },
    "US30": {
        "mt5":         "US30",
        "yf":          "^DJI",
        "price_lo":    30000,
        "price_hi":    50000,
        "sessions":    [0, 21],
        "decimals":    1,
        "min_sl":      65.0,
        "tier":        "US30 ELITE",
        "bias":        "BULL",
        "rr":          2.6,
        "sweep_bonus": 2,
        "wick_ratio":  1.5,
    },
}

SYMBOLS = ["XAU/USD", "NAS100", "DE30", "US30"]

# ============================================================
# CORE SETTINGS
# ============================================================
ATR_MULT               = 0.28
VOL_MULT               = 1.15
ADX_THRESHOLD          = 26
SIGNAL_COOLDOWN        = 7200
HTF_REFRESH            = 900
MAX_DAILY_LOSS         = -300
MAX_CONSECUTIVE_LOSSES = 3
MAIN_LOOP_DELAY        = 4

STDV_PERIOD         = 20
STDV_THRESHOLD_MULT = 1.15
AOX_FAST            = 5
AOX_SLOW            = 34

ENABLE_WIZARD_AI     = True
WIZARD_MIN_SCORE     = 20
WIZARD_VOLUME_MULT   = 1.5
WIZARD_ADX_THRESHOLD = 25

CORRELATION_BLOCK    = True
MAX_OPEN_CORRELATED  = 1
VOLATILITY_KILL      = True
FALSE_BREAK_FILTER   = True

# ============================================================
# EXECUTION SLIPPAGE BUFFER
# ============================================================
EXECUTION_BUFFER = {
    "XAU/USD": 0.20,
    "NAS100":  2.5,
    "DE30":    3.0,
    "US30":    2.5,
}

# ============================================================
# SCORE THRESHOLDS
# ============================================================
RANGE_MIN_SCORE = 7
TREND_MIN_SCORE = 8

# ============================================================
# MARKET STRUCTURE
# ============================================================
MARKET_STRUCTURE = {
    "XAU/USD": {
        "sweep_lookback":            6,
        "zone_lookback":             10,
        "displacement_mult":         1.20,
        "premium_discount_lookback": 24,
        "wick_ratio":                1.8,
    },
    "NAS100": {
        "sweep_lookback":            8,
        "zone_lookback":             12,
        "displacement_mult":         1.35,
        "premium_discount_lookback": 30,
        "wick_ratio":                2.0,
    },
    "DE30": {
        "sweep_lookback":            7,
        "zone_lookback":             14,
        "displacement_mult":         1.25,
        "premium_discount_lookback": 28,
        "wick_ratio":                1.9,
    },
    "US30": {
        "sweep_lookback":            8,
        "zone_lookback":             12,
        "displacement_mult":         1.30,
        "premium_discount_lookback": 28,
        "wick_ratio":                1.8,
    },
}

MARKET_MIN_STRUCTURE_SCORE = {
    "XAU/USD": 7,
    "NAS100":  8,
    "DE30":    7,
    "US30":    8,
}

# ============================================================
# SESSION CURATION
# ============================================================
ALLOWED_SESSIONS = [
    "Asian Precision",
    "London",
    "NY+London",
    "NY Killzone",
]

# ============================================================
# ATR MULTIPLIERS
# ============================================================
ATR_MARKET_MULTIPLIER = {
    "XAU/USD": 1.05,
    "NAS100":  1.03,
    "DE30":    1.08,
    "US30":    1.04,
}

DOLLAR_PER_POINT = {
    "XAU/USD": 100,
    "NAS100":  10,
    "DE30":    10,
    "US30":    10,
}

MAX_SPREAD = {
    "XAU/USD": 1.20,
    "NAS100":  4.0,
    "DE30":    5.0,
    "US30":    6.0,
}

REGIME_TIMEFRAME = {
    "SCALP":    "1M / 5M",
    "RANGE":    "15M / 30M",
    "TREND":    "1H / 4H",
    "BREAKOUT": "15M / 1H",
}

MAX_SIGNALS_PER_DAY = {
    "XAU/USD": 4,
    "NAS100":  3,
    "DE30":    2,
    "US30":    2,
}

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
        _htf_cache          = {
            s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS
        }
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
            f.write(
                f"{datetime.now(timezone.utc).isoformat()} | "
                f"{SYSTEM_VERSION} | ACTIVE"
            )
    except Exception as e:
        log.error(f"Watchdog failure: {e}")

# ============================================================
# LOG ROTATION
# ============================================================
def rotate_log():
    file_path = "signals_log.csv"
    try:
        if os.path.isfile(file_path):
            if os.path.getsize(file_path) > 5_000_000:
                os.rename(file_path, f"signals_log_{int(time.time())}.csv")
    except Exception as e:
        log.error(f"Log rotation failure: {e}")

# ============================================================
# SIGNAL LOGGER
# ============================================================
def log_signal(symbol, direction, score, rr, entry, sl, tp,
               session, regime, timeframe, signal_type):
    with log_lock:
        file_exists = os.path.isfile("signals_log.csv")
        with open(
            "signals_log.csv", "a", newline="", encoding="utf-8"
        ) as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "version", "timestamp", "symbol", "direction",
                    "score", "rr", "entry", "sl", "tp",
                    "session", "regime", "timeframe", "signal_type"
                ])
            writer.writerow([
                SYSTEM_VERSION,
                datetime.now(timezone.utc).isoformat(),
                symbol, direction, score, rr,
                entry, sl, tp, session, regime, timeframe, signal_type
            ])
        try:
            with open(
                "signals_backup.csv", "a", newline="", encoding="utf-8"
            ) as backup:
                csv.writer(backup).writerow([
                    SYSTEM_VERSION,
                    datetime.now(timezone.utc).isoformat(),
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
                json={
                    "chat_id":    CHAT_ID,
                    "text":       msg,
                    "parse_mode": "Markdown"
                },
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
    now = datetime.now(timezone.utc)
    wd  = now.weekday()
    hr  = now.hour
    if wd == 5:
        return True
    if wd == 6 and hr < 21:
        return True
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
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                threads=False
            )
            if raw.empty:
                log.error(f"{ticker} returned empty data")
                time.sleep(1)
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw.columns = [str(c).lower() for c in raw.columns]
            return raw[
                ["open", "high", "low", "close", "volume"]
            ].reset_index(drop=True)
        except Exception as e:
            log.error(f"YFinance fetch failed {ticker} | {attempt+1} | {e}")
            time.sleep(1)
    return None

def fetch_market_data(symbol_key):
    yf_sym = MARKETS[symbol_key]["yf"]
    if yf_sym:
        df = fetch_yf(yf_sym)
        if df is not None and len(df) > 100:
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
    recent    = df.tail(3)
    avg_range = (
        recent["high"].astype(float) - recent["low"].astype(float)
    ).mean()
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

    # WaveTrend oscillator
    hlc3           = (hi + lo + cl) / 3
    esa            = hlc3.ewm(span=10, adjust=False).mean()
    d              = (hlc3 - esa).abs().ewm(span=10, adjust=False).mean()
    ci             = (hlc3 - esa) / (0.015 * d)
    df["wt1"]      = ci.ewm(span=21, adjust=False).mean()
    df["wt2"]      = df["wt1"].rolling(4).mean()

    df.replace([float("inf"), float("-inf")], pd.NA, inplace=True)
    df.dropna(inplace=True)

    return df

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
    if last["ema21"] > last["ema50"]:
        trend = "BULL"
    elif last["ema21"] < last["ema50"]:
        trend = "BEAR"
    else:
        trend = MARKETS[symbol_key].get("bias", "NEUTRAL")
    cache["trend"] = trend
    cache["ts"]    = now
    return trend

# ============================================================
# MULTI-TIMEFRAME TREND (MTF)
# ============================================================
def mtf_bullish(symbol_key, df):
    """
    True when price is above EMA50, EMA200, and EMA9 > EMA21.
    Represents short, medium, and long term all aligned bullish.
    """
    if df is None or len(df) < 200:
        return False
    last = df.iloc[-1]
    return (
        float(last["ema9"])   > float(last["ema21"])
        and float(last["ema21"]) > float(last["ema50"])
        and float(last["close"]) > float(last["ema200"])
    )

def mtf_bearish(symbol_key, df):
    if df is None or len(df) < 200:
        return False
    last = df.iloc[-1]
    return (
        float(last["ema9"])   < float(last["ema21"])
        and float(last["ema21"]) < float(last["ema50"])
        and float(last["close"]) < float(last["ema200"])
    )

# ============================================================
# WAVETREND CONFIRMATION
# ============================================================
def wavetrend_confirmation(df, direction):
    """
    WaveTrend crossover confirmation:
    BUY  — wt1 crosses above wt2 from below -30 (oversold)
    SELL — wt1 crosses below wt2 from above +30 (overbought)
    """
    if len(df) < 5:
        return False
    wt1_now  = float(df.iloc[-1]["wt1"])
    wt2_now  = float(df.iloc[-1]["wt2"])
    wt1_prev = float(df.iloc[-2]["wt1"])
    wt2_prev = float(df.iloc[-2]["wt2"])

    if direction == "BUY":
        return (
            wt1_prev < wt2_prev
            and wt1_now > wt2_now
            and wt1_now < 20
        )
    elif direction == "SELL":
        return (
            wt1_prev > wt2_prev
            and wt1_now < wt2_now
            and wt1_now > -20
        )
    return False

# ============================================================
# WEEKLY / DAILY / H12 / H4 TREND APPROXIMATIONS
# ============================================================
def weekly_trend(df, direction):
    """Weekly: price vs 250-bar rolling mean (approx 1 week on 5m)."""
    if df is None or len(df) < 260:
        return False
    weekly_ma = df["close"].rolling(250).mean().iloc[-1]
    price     = float(df.iloc[-1]["close"])
    if pd.isna(weekly_ma):
        return False
    if direction == "BUY":
        return price > weekly_ma
    return price < weekly_ma

def daily_trend(df, direction):
    """Daily: price vs 200-bar EMA."""
    if df is None or len(df) < 210:
        return False
    last = df.iloc[-1]
    price = float(last["close"])
    ema200 = float(last["ema200"])
    if direction == "BUY":
        return price > ema200
    return price < ema200

def h12_trend(df, direction):
    """H12 approx: price vs 144-bar rolling mean."""
    if df is None or len(df) < 150:
        return False
    h12_ma = df["close"].rolling(144).mean().iloc[-1]
    price  = float(df.iloc[-1]["close"])
    if pd.isna(h12_ma):
        return False
    if direction == "BUY":
        return price > h12_ma
    return price < h12_ma

def h4_trend(df, direction):
    """H4 approx: price vs 50-bar EMA."""
    if df is None or len(df) < 55:
        return False
    last = df.iloc[-1]
    price = float(last["close"])
    ema50 = float(last["ema50"])
    if direction == "BUY":
        return price > ema50
    return price < ema50

# ============================================================
# QUANTUM MACRO FILTER
# ============================================================
def quantum_macro_filter(df, direction):
    """
    All 4 timeframe layers must align.
    Minimum 3/4 required for pass (prevents false rejections).
    """
    if df is None:
        return False

    score = 0
    if weekly_trend(df, direction): score += 3
    if daily_trend(df, direction):  score += 3
    if h12_trend(df, direction):    score += 2
    if h4_trend(df, direction):     score += 2

    return score >= 8

# ============================================================
# PATTERN DETECTION
# ============================================================
def fair_value_gap(df):
    if len(df) < 3:
        return False, False
    c1 = df.iloc[-3]
    c3 = df.iloc[-1]
    return (
        float(c1["high"]) < float(c3["low"]),
        float(c1["low"])  > float(c3["high"])
    )

def detect_choch(df):
    if len(df) < 6:
        return False, False
    highs = df["high"].tail(6).tolist()
    lows  = df["low"].tail(6).tolist()
    close = float(df.iloc[-1]["close"])
    return (
        lows[-2]  < lows[-3]  and close > highs[-2],
        highs[-2] > highs[-3] and close < lows[-2]
    )

def detect_liquidity_sweep(df, symbol_key):
    lookback  = MARKET_STRUCTURE[symbol_key]["sweep_lookback"]
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

def detect_displacement(df, symbol_key):
    if len(df) < 2:
        return False
    candle = df.iloc[-1]
    body   = abs(float(candle["close"]) - float(candle["open"]))
    return body > float(candle["atr"]) * MARKET_STRUCTURE[symbol_key]["displacement_mult"]

def detect_wick_rejection(df, atr, symbol_key):
    if len(df) < 2:
        return False, False
    candle      = df.iloc[-1]
    open_price  = float(candle["open"])
    close_price = float(candle["close"])
    high_price  = float(candle["high"])
    low_price   = float(candle["low"])
    body        = abs(close_price - open_price)
    if body < atr * 0.05:
        return False, False
    upper_wick = high_price - max(open_price, close_price)
    lower_wick = min(open_price, close_price) - low_price
    wick_ratio = MARKETS[symbol_key]["wick_ratio"]
    return lower_wick > body * wick_ratio, upper_wick > body * wick_ratio

def premium_discount(df, symbol_key):
    lookback = MARKET_STRUCTURE[symbol_key]["premium_discount_lookback"]
    if len(df) < lookback:
        return {"discount": False, "premium": False}
    recent   = df.tail(lookback)
    midpoint = (float(recent["high"].max()) + float(recent["low"].min())) / 2
    price    = float(df.iloc[-1]["close"])
    return {"discount": price < midpoint, "premium": price > midpoint}

# ============================================================
# BREAK OF STRUCTURE
# ============================================================
def break_of_structure(df, direction):
    """
    BUY  BOS: close breaks above prior swing high with momentum.
    SELL BOS: close breaks below prior swing low with momentum.
    """
    if len(df) < 10:
        return False
    atr   = float(df.iloc[-1]["atr"])
    close = float(df.iloc[-1]["close"])
    if direction == "BUY":
        swing_high = float(df["high"].iloc[-10:-1].max())
        return close > swing_high + atr * 0.10
    if direction == "SELL":
        swing_low = float(df["low"].iloc[-10:-1].min())
        return close < swing_low - atr * 0.10
    return False

# ============================================================
# INSTITUTIONAL VOLUME
# ============================================================
def institutional_volume(df):
    """Volume is at least 1.8x the 20-bar average — institutional activity."""
    if len(df) < 21:
        return False
    last  = df.iloc[-1]
    vol   = float(last["volume"])
    volma = float(last["volma"]) if not pd.isna(last["volma"]) else 0
    return volma > 0 and vol > volma * 1.8

# ============================================================
# STRONG CANDLE
# ============================================================
def strong_candle(df, direction):
    """
    Body is at least 60% of total candle range
    and candle closes in the top/bottom 30% of its range.
    """
    if len(df) < 2:
        return False
    candle     = df.iloc[-1]
    open_p     = float(candle["open"])
    close_p    = float(candle["close"])
    high_p     = float(candle["high"])
    low_p      = float(candle["low"])
    body       = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0:
        return False
    body_ratio = body / total_range
    if body_ratio < 0.60:
        return False
    if direction == "BUY":
        return close_p > (low_p + total_range * 0.70)
    if direction == "SELL":
        return close_p < (low_p + total_range * 0.30)
    return False

# ============================================================
# INSTITUTIONAL STRUCTURE SCORE
# ============================================================
def institutional_structure_score(df, symbol_key):
    bull_sweep,  bear_sweep  = detect_liquidity_sweep(df, symbol_key)
    bull_wick,   bear_wick   = detect_wick_rejection(
        df, float(df.iloc[-1]["atr"]), symbol_key
    )
    displacement = detect_displacement(df, symbol_key)
    pd_zone      = premium_discount(df, symbol_key)

    buy_score  = 0
    sell_score = 0
    buy_cond   = {}
    sell_cond  = {}

    if bull_sweep:
        buy_score += 2; buy_cond["SWEEP"] = True
    if bull_wick:
        buy_score += 2; buy_cond["WICK"] = True
    if detect_zone_retest(df, symbol_key, "BUY"):
        buy_score += 2; buy_cond["ZONE"] = True
    if displacement:
        buy_score += 2; buy_cond["DISPLACEMENT"] = True
    if pd_zone["discount"]:
        buy_score += 1; buy_cond["DISCOUNT"] = True

    if bear_sweep:
        sell_score += 2; sell_cond["SWEEP"] = True
    if bear_wick:
        sell_score += 2; sell_cond["WICK"] = True
    if detect_zone_retest(df, symbol_key, "SELL"):
        sell_score += 2; sell_cond["ZONE"] = True
    if displacement:
        sell_score += 2; sell_cond["DISPLACEMENT"] = True
    if pd_zone["premium"]:
        sell_score += 1; sell_cond["PREMIUM"] = True

    if buy_score  >= 8: buy_score  += 1
    if sell_score >= 8: sell_score += 1

    return buy_cond, sell_cond, buy_score, sell_score

def detect_supply_demand_zones(df):
    if len(df) < 20:
        return None, None
    recent = df.tail(20)
    return (
        recent["low"].rolling(5).min().iloc[-1],
        recent["high"].rolling(5).max().iloc[-1],
    )

def detect_market_regime(df):
    adx = float(df.iloc[-1]["adx"])
    if adx >= 35:  return "BREAKOUT"
    elif adx >= 25: return "TREND"
    else:           return "RANGE"

def get_signal_number(symbol_key, session):
    global _signal_counter
    if _signal_counter[symbol_key]["session"] != session:
        _signal_counter[symbol_key]["session"] = session
        _signal_counter[symbol_key]["count"]   = 1
    else:
        _signal_counter[symbol_key]["count"] += 1
    n = _signal_counter[symbol_key]["count"]
    entry_type = (
        "PRIMARY BREAKOUT"       if n == 1 else
        "SECONDARY RETEST"       if n == 2 else
        "ADVANCED CONTINUATION"
    )
    return n, entry_type

# ============================================================
# SESSION FILTER
# ============================================================
def in_session(symbol_key):
    h = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]
    if not (s <= h < e):
        return False, "Closed"
    if 1  <= h < 6:  return True, "Asian Precision"
    if 8  <= h < 11: return True, "London"
    if 13 <= h < 15: return True, "NY Killzone"
    if 14 <= h < 16: return True, "NY+London"
    return False, "Closed"

# ============================================================
# SPREAD / VOLATILITY CHECKS
# ============================================================
def spread_too_high(symbol_key, spread):
    return spread > MAX_SPREAD[symbol_key] * 0.90

def volatility_danger(df, symbol_key):
    """
    ATR > 1.15x its 50-bar average = dangerous volatility.
    ATR > 2.0x its 50-bar average = extreme danger, always block.
    """
    if len(df) < 60:
        return False
    atr     = float(df.iloc[-1]["atr"])
    atr_avg = df["atr"].rolling(50).mean().iloc[-1]
    if pd.isna(atr_avg) or atr_avg == 0:
        return False
    ratio = atr / atr_avg
    # Block extreme volatility always; moderate only during Asia
    return ratio > 2.0

def quantum_volatility_ok(df):
    """Returns True when volatility is healthy (not too low, not extreme)."""
    if len(df) < 60:
        return False
    atr     = float(df.iloc[-1]["atr"])
    atr_avg = df["atr"].rolling(50).mean().iloc[-1]
    if pd.isna(atr_avg) or atr_avg == 0:
        return False
    ratio = atr / atr_avg
    return 0.85 <= ratio <= 1.80

# ============================================================
# FALSE BREAKOUT FILTER
# ============================================================
def false_breakout_filter(df, direction):
    if len(df) < 3:
        return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if direction == "BUY":
        return (
            float(last["close"]) > float(prev["high"])
            and float(last["low"]) > float(prev["low"])
        )
    if direction == "SELL":
        return (
            float(last["close"]) < float(prev["low"])
            and float(last["high"]) < float(prev["high"])
        )
    return False

# ============================================================
# CORRELATION BLOCKER
# ============================================================
CORRELATED_GROUPS = [["NAS100", "US30", "DE30"]]

def correlated_signal_block(symbol_key):
    if not CORRELATION_BLOCK:
        return False
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
        "XAU/USD": 5400,
        "NAS100":  7200,
        "DE30":    14400,
        "US30":    7200,
    }
    cooldown = duplicate_windows.get(symbol_key, 5400)
    with signal_lock:
        last_dir  = _last_signal_direction.get(symbol_key)
        last_time = _last_signal_time.get(symbol_key, 0)
        if last_dir == direction and now - last_time < cooldown:
            remaining = int(cooldown - (now - last_time))
            log.info(
                f"Duplicate blocked {symbol_key} ({remaining}s remaining)"
            )
            return True
        _last_signal_direction[symbol_key] = direction
        _last_signal_time[symbol_key]      = now
    return False

def economic_news_block():
    return False

# ============================================================
# BUILD BASE SCORE
# ============================================================
def build_score(df, trend, symbol_key):
    last   = df.iloc[-1]
    rsi    = float(last["rsi"])
    ema9   = float(last["ema9"])
    ema21  = float(last["ema21"])
    ema50  = float(last["ema50"])
    ema200 = float(last["ema200"])
    adx    = float(last["adx"])
    vol    = float(last["volume"])
    volma  = float(last["volma"]) if not pd.isna(last["volma"]) else 0
    atr    = float(last["atr"])
    stdv   = float(last["stdv"])   if not pd.isna(last["stdv"])   else 0
    aox    = float(last["aox"])    if not pd.isna(last["aox"])    else 0

    stdv_ma = (
        df["stdv"].rolling(STDV_PERIOD).mean().iloc[-1]
        if len(df) > STDV_PERIOD else 0
    )

    bull_fvg,   bear_fvg   = fair_value_gap(df)
    bull_choch, bear_choch = detect_choch(df)
    bull_sweep, bear_sweep = detect_liquidity_sweep(df, symbol_key)
    bull_wick,  bear_wick  = detect_wick_rejection(df, atr, symbol_key)

    bullish_break = float(last["close"]) > float(df.iloc[-2]["high"]) + atr * 0.12
    bearish_break = float(last["close"]) < float(df.iloc[-2]["low"])  - atr * 0.12

    buy = {
        "HTF":   trend == "BULL",
        "EMA":   ema9 > ema21 > ema50 > ema200,
        "RSI":   56 <= rsi <= 72,
        "ADX":   adx > ADX_THRESHOLD,
        "VOL":   volma > 0 and vol > volma * VOL_MULT,
        "FVG":   bull_fvg,
        "CHOCH": bull_choch,
        "BOS":   bullish_break,
        "SWEEP": bull_sweep,
        "WICK":  bull_wick,
        "STDV":  stdv_ma > 0 and stdv > stdv_ma * STDV_THRESHOLD_MULT,
        "AOX":   aox > 0,
    }

    sell = {
        "HTF":   trend == "BEAR",
        "EMA":   ema9 < ema21 < ema50 < ema200,
        "RSI":   30 <= rsi <= 44,
        "ADX":   adx > ADX_THRESHOLD,
        "VOL":   volma > 0 and vol > volma * VOL_MULT,
        "FVG":   bear_fvg,
        "CHOCH": bear_choch,
        "BOS":   bearish_break,
        "SWEEP": bear_sweep,
        "WICK":  bear_wick,
        "STDV":  stdv_ma > 0 and stdv > stdv_ma * STDV_THRESHOLD_MULT,
        "AOX":   aox < 0,
    }

    buy_score  = sum(buy.values())
    sell_score = sum(sell.values())

    if buy["STDV"]  and buy["AOX"]:   buy_score  += 1
    if sell["STDV"] and sell["AOX"]:  sell_score += 1

    sweep_bonus = MARKETS[symbol_key]["sweep_bonus"]
    if bull_sweep and bull_wick: buy_score  += sweep_bonus
    if bear_sweep and bear_wick: sell_score += sweep_bonus

    if symbol_key == "XAU/USD":
        if bull_sweep: buy_score  += 1
        if bear_sweep: sell_score += 1
        if bull_wick:  buy_score  += 1
        if bear_wick:  sell_score += 1

    if adx >= 35:
        if   buy_score > sell_score: buy_score  += 1
        elif sell_score > buy_score: sell_score += 1

    return buy, sell, buy_score, sell_score

# ============================================================
# WIZARD AI
# ============================================================
def wizard_ai_confirmation(df, symbol_key, direction):
    if len(df) < 250:
        return False, 0

    last   = df.iloc[-1]
    close  = float(last["close"])
    ema50  = float(last["ema50"])
    ema200 = float(last["ema200"])
    rsi    = float(last["rsi"])
    adx    = float(last["adx"])
    volume = float(last["volume"])
    volma  = float(last["volma"]) if not pd.isna(last["volma"]) else 0
    aox    = float(last["aox"])   if not pd.isna(last["aox"])   else 0

    score = 0

    if direction == "BUY":
        if close > ema50:               score += 3
        if ema50  > ema200:             score += 3
        if rsi    > 55:                 score += 2
        if adx    > WIZARD_ADX_THRESHOLD: score += 2
        if aox    > 0:                  score += 2
    elif direction == "SELL":
        if close < ema50:               score += 3
        if ema50  < ema200:             score += 3
        if rsi    < 45:                 score += 2
        if adx    > WIZARD_ADX_THRESHOLD: score += 2
        if aox    < 0:                  score += 2

    if volma > 0 and volume > volma * WIZARD_VOLUME_MULT:
        score += 3

    bull_fvg, bear_fvg     = fair_value_gap(df)
    bull_choch, bear_choch = detect_choch(df)
    bull_sweep, bear_sweep = detect_liquidity_sweep(df, symbol_key)
    bull_wick, bear_wick   = detect_wick_rejection(
        df, float(last["atr"]), symbol_key
    )

    if direction == "BUY":
        if bull_fvg:   score += 2
        if bull_choch: score += 2
        if bull_sweep: score += 3
        if bull_wick:  score += 2
    elif direction == "SELL":
        if bear_fvg:   score += 2
        if bear_choch: score += 2
        if bear_sweep: score += 3
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

    rsi   = float(last["rsi"])
    adx   = float(last["adx"])
    vol   = float(last["volume"])
    volma = float(last["volma"]) if not pd.isna(last["volma"]) else 0

    bull_sweep, bear_sweep = detect_liquidity_sweep(df, symbol_key)
    bull_fvg,   bear_fvg   = fair_value_gap(df)

    # MTF alignment
    if direction == "BUY"  and mtf_bullish(symbol_key, df):  score += 6
    if direction == "SELL" and mtf_bearish(symbol_key, df):  score += 6

    # WaveTrend
    if wavetrend_confirmation(df, direction): score += 3

    # Liquidity sweep
    if direction == "BUY"  and bull_sweep: score += 3
    if direction == "SELL" and bear_sweep: score += 3

    # FVG
    if direction == "BUY"  and bull_fvg: score += 2
    if direction == "SELL" and bear_fvg: score += 2

    # Break of structure
    if break_of_structure(df, direction): score += 3

    # Institutional volume
    if institutional_volume(df): score += 2

    # Strong candle
    if strong_candle(df, direction): score += 2

    # RSI and ADX
    if direction == "BUY"  and rsi > 60: score += 3
    if direction == "SELL" and rsi < 40: score += 3
    if adx > 30: score += 3

    # Extra volume surge
    if volma > 0 and vol > volma * 1.7: score += 4

    return score

# ============================================================
# DETERMINE BEST DIRECTION
# ============================================================
def determine_best_direction(buy_score, sell_score):
    if buy_score >= sell_score:
        return "BUY"
    return "SELL"

# ============================================================
# TRADE QUALITY RANKING
# ============================================================
def trade_quality(score):
    if   score >= 30: return "GOD-TIER"
    elif score >= 26: return "ELITE"
    elif score >= 22: return "HIGH-PROBABILITY"
    return "STANDARD"

# ============================================================
# ADAPTIVE RISK
# ============================================================
def adaptive_risk(session):
    if   session == "Asian Precision": return 0.5
    elif session == "London":          return 1.0
    elif session == "NY Killzone":     return 1.2
    return 1.0

# ============================================================
# DYNAMIC RR
# ============================================================
def get_dynamic_rr(symbol_key, regime):
    return RR_PROFILE.get(symbol_key, {}).get(
        regime, MARKETS[symbol_key]["rr"]
    )

# ============================================================
# LEVELS
# ============================================================
def calc_levels(price, atr, symbol_key, df, direction, regime):
    min_sl   = MARKETS[symbol_key]["min_sl"]
    decimals = MARKETS[symbol_key]["decimals"]
    recent   = df.tail(8)

    swing_dist = (
        price - float(recent["low"].min())
        if direction == "BUY"
        else float(recent["high"].max()) - price
    )

    atr_sl  = atr * ATR_MULT * ATR_MARKET_MULTIPLIER[symbol_key]
    sl_dist = max(
        min_sl,
        min(max(atr_sl, swing_dist * 0.85), swing_dist * 1.15)
    )

    if symbol_key == "DE30":
        sl_dist *= 1.35 if regime == "BREAKOUT" else 1.25

    rr = get_dynamic_rr(symbol_key, regime)

    if direction == "BUY":
        sl = price - sl_dist
        tp = price + sl_dist * rr
    else:
        sl = price + sl_dist
        tp = price - sl_dist * rr

    return (
        round(sl, decimals),
        round(tp, decimals),
        round(sl_dist, decimals),
        rr
    )

# ============================================================
# LOT SIZE
# ============================================================
def lot_for_risk(price, sl, symbol_key, risk_multiplier=1.0):
    base_risk = 50
    risk      = base_risk * risk_multiplier
    sl_dist   = abs(price - sl)
    if sl_dist <= 0:
        return 0.01
    lot = risk / (sl_dist * DOLLAR_PER_POINT[symbol_key])
    caps = {
        "XAU/USD": 1.50,
        "NAS100":  2.00,
        "DE30":    1.50,
        "US30":    1.50,
    }
    return round(max(0.01, min(lot, caps[symbol_key])), 3)

# ============================================================
# MASTER SIGNAL ENGINE
# ============================================================
def master_signal(symbol_key, df, session, trend, regime,
                  buy, sell, buy_score, sell_score,
                  structure_buy_score, structure_sell_score):

    direction = determine_best_direction(buy_score, sell_score)
    best      = max(buy_score, sell_score)

    # Quantum macro filter
    if not quantum_macro_filter(df, direction):
        log.info(f"REJECTED {symbol_key} quantum macro filter")
        return None, None, None

    # Wizard AI
    if ENABLE_WIZARD_AI:
        wizard_pass, wizard_score = wizard_ai_confirmation(
            df, symbol_key, direction
        )
        if not wizard_pass:
            log.info(
                f"REJECTED {symbol_key} Wizard AI failed | "
                f"Score: {wizard_score}"
            )
            return None, None, None
        best += int(wizard_score * 0.30)
    else:
        wizard_score = 0

    # Ultra sniper
    sniper = ultra_sniper_score(df, symbol_key, direction)
    best  += sniper

    # Session threshold
    required = SESSION_THRESHOLDS.get(session, 20)
    if best < required:
        log.info(
            f"REJECTED {symbol_key} session score too low "
            f"({best} < {required})"
        )
        return None, None, None

    # Quantum volatility
    if VOLATILITY_KILL:
        if not quantum_volatility_ok(df):
            log.info(f"REJECTED {symbol_key} quantum volatility filter")
            return None, None, None

    # False breakout
    if FALSE_BREAK_FILTER:
        if not false_breakout_filter(df, direction):
            log.info(f"REJECTED {symbol_key} false breakout filter")
            return None, None, None

    return direction, best, wizard_score

# ============================================================
# EXECUTE TRADE — sends Telegram signal
# ============================================================
def execute_trade(symbol_key, df, direction, best, wizard_score,
                  sniper_score, macro_trend, session, trend,
                  regime, buy, sell, source, asia_mode):

    price = float(df.iloc[-1]["close"])
    atr   = float(df.iloc[-1]["atr"])
    rsi   = float(df.iloc[-1]["rsi"])
    adx   = float(df.iloc[-1]["adx"])
    dec   = MARKETS[symbol_key]["decimals"]

    demand_zone, supply_zone = detect_supply_demand_zones(df)

    if direction == "BUY":
        price += EXECUTION_BUFFER[symbol_key]
    else:
        price -= EXECUTION_BUFFER[symbol_key]

    sl, tp, sl_dist, rr = calc_levels(
        price, atr, symbol_key, df, direction, regime
    )

    risk_mult = adaptive_risk(session)
    lot       = lot_for_risk(price, sl, symbol_key, risk_mult)

    quality        = trade_quality(best)
    timeframe      = REGIME_TIMEFRAME.get(regime, "1H / 4H")
    signal_num, entry_type = get_signal_number(symbol_key, session)

    log_signal(
        symbol_key, direction, best, rr, price, sl, tp,
        session, regime, timeframe, "CONTINUATION"
    )
    sync_real_pnl()

    checks    = buy if direction == "BUY" else sell
    cond_text = "\n".join([f" {k}" for k, v in checks.items() if v])
    if demand_zone:
        cond_text += "\n DEMAND_ZONE"
    if supply_zone:
        cond_text += "\n SUPPLY_ZONE"

    action_emoji = "📈" if direction == "BUY" else "📉"

    # Priority badge
    priority_tag = (
        "🔱 *PRIORITY MARKET*\n"
        if symbol_key in PRIORITY_MARKETS else ""
    )

    msg = (
        f"🎯 *{SYSTEM_VERSION}* | INSTITUTIONAL EXECUTION\n"
        f"*{MARKETS[symbol_key]['mt5']}* | "
        f"⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n"
        f"{priority_tag}\n"
        f"🔥 *Action:* {direction} {action_emoji}\n"
        f"🎯 *Signal #:* {signal_num}\n"
        f"📍 *Entry Type:* {entry_type}\n"
        f"🚀 *Signal Type:* CONTINUATION\n"
        f"⭐ *Total Score:* {best}\n"
        f"🏆 *Trade Quality:* {quality}\n"
        f"🌍 *Macro Trend:* {macro_trend}\n"
        f"⚛ *Quantum Filter:* PASS\n"
        f"🎯 *Sniper Score:* {sniper_score}\n"
        f"🧠 *Wizard AI Score:* "
        f"{wizard_score if ENABLE_WIZARD_AI else 'OFF'}\n"
        f"🧠 *Regime:* {regime}\n"
        f"⏱ *Timeframe:* {timeframe}\n"
        f"📊 *Market Bias:* {MARKETS[symbol_key]['bias']}\n\n"
        f"📍 *Entry:* {price:,.{dec}f}\n"
        f"🛑 *SL:* {sl:,.{dec}f}\n"
        f"🎯 *TP:* {tp:,.{dec}f} *(1:{rr} RR)*\n\n"
        f"📈 *RSI:* {rsi:.1f}\n"
        f"📉 *ADX:* {adx:.1f}\n"
        f"🌍 *Trend:* {trend}\n"
        f"⏰ *Session:* {session}\n"
        f"🧠 *Mode:* "
        f"{'ASIA ELITE PRECISION' if asia_mode else 'CORE INSTITUTIONAL'}\n"
        f"📡 *Source:* {source}\n\n"
        f"💵 *Lot:* {lot}\n\n"
        f"✅ *Conditions:*\n"
        f"{cond_text}\n\n"
        f"🛡 *ELITE INSTITUTIONAL FILTER ACTIVE*\n"
        f"⚡ *ULTIMATE HYBRID SUPREME*"
    )

    send_telegram(msg)

    log.info(
        f"SIGNAL SENT {symbol_key} {direction} | "
        f"Entry: {price} | SL: {sl} | TP: {tp} | RR: {rr} | "
        f"Quality: {quality} | Sniper: {sniper_score} | "
        f"Signal#: {signal_num} | Regime: {regime}"
    )

# ============================================================
# PROCESS SYMBOL
# ============================================================
def process_symbol(symbol_key):
    log.info(f"Scanning {symbol_key}")

    if _daily_signal_count[symbol_key] >= MAX_SIGNALS_PER_DAY[symbol_key]:
        log.info(f"REJECTED {symbol_key} daily cap reached")
        return

    if weekend_block(symbol_key):  return
    if daily_loss_lock():          return
    if loss_streak_lock():         return

    watchdog()
    rotate_log()

    ok, session = in_session(symbol_key)
    if not ok:
        return

    if session not in ALLOWED_SESSIONS:
        log.info(f"REJECTED {symbol_key} outside session ({session})")
        return

    if economic_news_block():
        return

    df, source = get_entry_data(symbol_key)
    if df is None or len(df) < 100:
        return

    spread = get_spread(df)
    if spread_too_high(symbol_key, spread):
        log.info(f"REJECTED {symbol_key} spread {spread:.4f}")
        return

    df = add_ind(df)
    if df is None or len(df) < 50:
        log.info(f"REJECTED {symbol_key} insufficient data after indicators")
        return

    if volatility_danger(df, symbol_key):
        log.info(f"REJECTED {symbol_key} extreme volatility danger")
        return

    price = float(df.iloc[-1]["close"])
    atr   = float(df.iloc[-1]["atr"])

    if price <= 0:
        return

    if not (MARKETS[symbol_key]["price_lo"] <= price
            <= MARKETS[symbol_key]["price_hi"]):
        log.info(f"REJECTED {symbol_key} price out of range")
        return

    trend  = get_trend(symbol_key)
    regime = detect_market_regime(df)

    # Macro trend for Telegram display
    macro_trend = (
        "BULL" if weekly_trend(df, "BUY") and daily_trend(df, "BUY")
        else "BEAR" if weekly_trend(df, "SELL") and daily_trend(df, "SELL")
        else "NEUTRAL"
    )

    asia_mode = session == "Asian Precision"

    buy, sell, buy_score, sell_score = build_score(df, trend, symbol_key)

    struct_buy, struct_sell, struct_buy_score, struct_sell_score = (
        institutional_structure_score(df, symbol_key)
    )

    buy.update(struct_buy)
    sell.update(struct_sell)
    buy_score  += struct_buy_score
    sell_score += struct_sell_score

    # Asia bonus
    if asia_mode:
        buy_score  += 1 if buy_score  >= 9 else 0
        sell_score += 1 if sell_score >= 9 else 0

    # Asia Elite Filter
    if asia_mode:
        asia_spread_cap = MAX_SPREAD[symbol_key] * 0.75
        if spread > asia_spread_cap:
            log.info(f"REJECTED {symbol_key} Asia spread too high")
            return
        if symbol_key in ["NAS100", "US30", "DE30"]:
            if max(buy_score, sell_score) < 11:
                log.info(f"REJECTED {symbol_key} weak Asia index score")
                return
        if symbol_key == "XAU/USD":
            if max(buy_score, sell_score) < 10:
                log.info(f"REJECTED {symbol_key} weak Asia gold score")
                return

    log.info(
        f"{symbol_key} | BUY: {buy_score} | SELL: {sell_score} | "
        f"Regime: {regime} | Trend: {trend} | Session: {session}"
    )

    best_structure = max(struct_buy_score, struct_sell_score)
    if best_structure < MARKET_MIN_STRUCTURE_SCORE[symbol_key]:
        log.info(f"REJECTED {symbol_key} weak structure score")
        return

    direction = determine_best_direction(buy_score, sell_score)

    if trend == "BULL" and direction == "SELL":
        log.info(f"REJECTED {symbol_key} countertrend SELL")
        return
    if trend == "BEAR" and direction == "BUY":
        log.info(f"REJECTED {symbol_key} countertrend BUY")
        return

    demand_zone, supply_zone = detect_supply_demand_zones(df)
    planned_entry = float(df.iloc[-2]["close"])
    max_entry_drift = atr * (
        0.25 if symbol_key == "XAU/USD"
        else 0.30 if symbol_key == "DE30"
        else 0.35
    )

    if direction == "SELL" and supply_zone:
        if price < supply_zone * 0.998:
            log.info(f"REJECTED {symbol_key} weak supply rejection")
            return
    if direction == "BUY" and demand_zone:
        if price > demand_zone * 1.002:
            log.info(f"REJECTED {symbol_key} weak demand rejection")
            return
    if direction == "SELL" and price < planned_entry - max_entry_drift:
        log.info(f"REJECTED {symbol_key} late SELL drift")
        return
    if direction == "BUY" and price > planned_entry + max_entry_drift:
        log.info(f"REJECTED {symbol_key} late BUY drift")
        return

    # Correlation blocker
    if correlated_signal_block(symbol_key):
        return

    # Master signal engine
    direction, best, wizard_score = master_signal(
        symbol_key, df, session, trend, regime,
        buy, sell, buy_score, sell_score,
        struct_buy_score, struct_sell_score
    )

    if direction is None:
        return

    sniper_score = ultra_sniper_score(df, symbol_key, direction)

    if duplicate_signal(symbol_key, direction):
        return

    now = time.time()
    if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
        remaining = int(SIGNAL_COOLDOWN - (now - _signal_sent[symbol_key]))
        log.info(f"REJECTED {symbol_key} cooldown {remaining}s")
        return

    with signal_lock:
        _signal_sent[symbol_key]        = now
        _daily_signal_count[symbol_key] += 1

    execute_trade(
        symbol_key, df, direction, best, wizard_score,
        sniper_score, macro_trend, session, trend,
        regime, buy, sell, source, asia_mode
    )

# ============================================================
# MAIN LOOP
# ============================================================
def main():
    log.info(f"{SYSTEM_VERSION} STARTED")
    send_telegram(
        f"🚀 *{SYSTEM_VERSION} LIVE*\n\n"
        f"📊 *Markets Active:*\n"
        f"🥇 XAU/USD\n"
        f"📈 NAS100\n"
        f"🇩🇪 DE30\n"
        f"🇺🇸 US30\n\n"
        f"🔱 Priority Markets: XAU/USD, NAS100, US30\n\n"
        f"✅ Quantum Macro Filter\n"
        f"🎯 Ultra Sniper Score\n"
        f"⚛ WaveTrend Confirmation\n"
        f"🌍 MTF Trend Alignment\n"
        f"📊 Dynamic RR Engine\n"
        f"💰 Adaptive Risk Engine\n"
        f"🔒 Correlation Blocker\n"
        f"🚫 False Breakout Filter\n"
        f"🏆 Trade Quality Ranking\n"
        f"🧠 Wizard AI Active\n"
        f"🛡 Asia Elite Precision\n"
        f"🧵 Thread Safe\n"
        f"⚡ ULTIMATE HYBRID SUPREME LIVE"
    )

    while True:
        try:
            reset_daily()

            # Priority markets first
            ordered = PRIORITY_MARKETS + [
                s for s in SYMBOLS if s not in PRIORITY_MARKETS
            ]

            with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
                futures = []
                for symbol in ordered:
                    futures.append(
                        executor.submit(process_symbol, symbol)
                    )
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
