# ============================================================
# PEPPERSTONE MOMENTUM HUNTER v22.1-INSTITUTIONAL-CONTINUATION-ONLY
# GOLD + NAS100 + DE30 + US30
# PURE CONTINUATION | MAX WINRATE ENGINE
# ============================================================

import time
import logging
import requests
import pandas as pd
import ta
import os
import csv
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

SYSTEM_VERSION = "v22.1-INSTITUTIONAL-CONTINUATION-ONLY"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v22.1-continuation")

TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

# ============================================================
# MARKETS
# ============================================================
MARKETS = {
    "XAU/USD": {
        "mt5":        "XAUUSD.Qraw",
        "yf":         "GC=F",
        "price_lo":   4000,
        "price_hi":   7000,
        "sessions":   [7, 20],
        "decimals":   2,
        "min_sl":     7.0,
        "tier":       "GOLD ELITE",
        "bias":       "BULL",
        "rr":         2.0,
        "sweep_bonus": 3,
        "wick_ratio": 1.8,
    },
    "NAS100": {
        "mt5":        "NAS100",
        "yf":         "^NDX",
        "price_lo":   15000,
        "price_hi":   30000,
        "sessions":   [13, 21],
        "decimals":   1,
        "min_sl":     55.0,
        "tier":       "NASDAQ ELITE",
        "bias":       "BULL",
        "rr":         2.0,
        "sweep_bonus": 2,
        "wick_ratio": 1.6,
    },
    "DE30": {
        "mt5":        "DE30.Qraw",
        "yf":         "^GDAXI",
        "price_lo":   15000,
        "price_hi":   25000,
        "sessions":   [7, 18],
        "decimals":   1,
        "min_sl":     50.0,
        "tier":       "DE30 ELITE",
        "bias":       "BULL",
        "rr":         2.0,
        "sweep_bonus": 3,
        "wick_ratio": 1.7,
    },
    "US30": {
        "mt5":        "US30",
        "yf":         "^DJI",
        "price_lo":   30000,
        "price_hi":   50000,
        "sessions":   [13, 21],
        "decimals":   1,
        "min_sl":     65.0,
        "tier":       "US30 ELITE",
        "bias":       "BULL",
        "rr":         2.0,
        "sweep_bonus": 2,
        "wick_ratio": 1.5,
    },
    "NIFTY50": {
        "mt5":        "NIFTY50",
        "yf":         "^NSEI",
        "price_lo":   18000,
        "price_hi":   30000,
        "sessions":   [3, 10],
        "decimals":   1,
        "min_sl":     25,
        "tier":       "NIFTY ELITE",
        "bias":       "BULL",
        "rr":         2.0,
        "wick_ratio": 1.8,
    },
    "BANKNIFTY": {
        "mt5":        "BANKNIFTY",
        "yf":         "^NSEBANK",
        "price_lo":   35000,
        "price_hi":   70000,
        "sessions":   [3, 10],
        "decimals":   1,
        "min_sl":     45,
        "tier":       "BANKNIFTY ELITE",
        "bias":       "BULL",
        "rr":         2.0,
        "wick_ratio": 1.8,
    },
}

SYMBOLS = [
    "XAU/USD",
    "NAS100",
    "DE30",
    "US30",
    "NIFTY50",
    "BANKNIFTY",
]

# ============================================================
# CORE SETTINGS
# ============================================================
ATR_MULT               = 0.28
VOL_MULT               = 1.05
ADX_THRESHOLD          = 24
SIGNAL_COOLDOWN        = 3600
HTF_REFRESH            = 900
MAX_DAILY_LOSS         = -300
MAX_CONSECUTIVE_LOSSES = 3
MAIN_LOOP_DELAY        = 2

# ============================================================
# EXECUTION SLIPPAGE BUFFER
# ============================================================
EXECUTION_BUFFER = {
    "XAU/USD":   0.20,
    "NAS100":    2.5,
    "DE30":      3.0,
    "US30":      2.5,
    "NIFTY50":   2.0,
    "BANKNIFTY": 3.0,
}

# ============================================================
# MARKET STRUCTURE — CANDLE HISTORY SETTINGS
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
    "NIFTY50": {
        "sweep_lookback":            6,
        "zone_lookback":             10,
        "displacement_mult":         1.20,
        "premium_discount_lookback": 24,
        "wick_ratio":                1.8,
    },
    "BANKNIFTY": {
        "sweep_lookback":            6,
        "zone_lookback":             10,
        "displacement_mult":         1.25,
        "premium_discount_lookback": 24,
        "wick_ratio":                1.8,
    },
}

# ============================================================
# SESSION CURATION
# ============================================================
LONDON_NY_ONLY = [
    "London",
    "NY+London",
    "NY Killzone",
    "India",
]

# ============================================================
# ATR MULTIPLIERS
# ============================================================
ATR_MARKET_MULTIPLIER = {
    "XAU/USD":   1.05,
    "NAS100":    1.03,
    "DE30":      1.08,
    "US30":      1.04,
    "NIFTY50":   1.05,
    "BANKNIFTY": 1.06,
}

# ============================================================
# DOLLAR PER POINT
# ============================================================
DOLLAR_PER_POINT = {
    "XAU/USD":   100,
    "NAS100":    10,
    "DE30":      10,
    "US30":      10,
    "NIFTY50":   10,
    "BANKNIFTY": 10,
}

# ============================================================
# MAX SPREAD
# ============================================================
MAX_SPREAD = {
    "XAU/USD":   1.20,
    "NAS100":    4.0,
    "DE30":      5.0,
    "US30":      6.0,
    "NIFTY50":   3.0,
    "BANKNIFTY": 4.0,
}

# ============================================================
# MODE TO TIMEFRAME MAP
# ============================================================
MODE_TIMEFRAME = {
    "RANGE":    "15M / 30M",
    "TREND":    "1H / 4H",
    "REVERSAL": "15M / 1H",
}

# ============================================================
# STATE
# ============================================================
daily_pnl              = 0
consecutive_losses     = 0
last_reset_day         = datetime.now(timezone.utc).day

_signal_sent           = {s: 0 for s in SYMBOLS}
_htf_cache             = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}
_last_signal_direction = {}
_last_signal_time      = {}
_signal_counter        = {s: {"session": None, "count": 0} for s in SYMBOLS}

# ============================================================
# DAILY RESET & TRADE TRACKING
# ============================================================
def reset_daily():
    global daily_pnl, consecutive_losses, last_reset_day
    current_day = datetime.now(timezone.utc).day
    if current_day != last_reset_day:
        daily_pnl          = 0
        consecutive_losses = 0
        last_reset_day     = current_day
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
        with open("heartbeat.txt", "w") as f:
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
    if os.path.isfile(file_path):
        if os.path.getsize(file_path) > 5_000_000:
            os.rename(file_path, f"signals_log_{int(time.time())}.csv")

# ============================================================
# SIGNAL LOGGER WITH BACKUP FAILSAFE
# ============================================================
def log_signal(symbol, direction, score, rr, entry, sl, tp,
               session, mode, timeframe, signal_type):
    file_exists = os.path.isfile("signals_log.csv")
    with open("signals_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "version", "timestamp", "symbol", "direction",
                "score", "rr", "entry", "sl", "tp",
                "session", "mode", "timeframe", "signal_type"
            ])
        writer.writerow([
            SYSTEM_VERSION,
            datetime.now(timezone.utc).isoformat(),
            symbol, direction, score, rr,
            entry, sl, tp, session, mode, timeframe, signal_type
        ])

    try:
        with open("signals_backup.csv", "a", newline="") as backup:
            backup_writer = csv.writer(backup)
            backup_writer.writerow([
                SYSTEM_VERSION,
                datetime.now(timezone.utc).isoformat(),
                symbol, direction, score, rr,
                entry, sl, tp, session,
                mode, timeframe, signal_type
            ])
    except Exception as e:
        log.error(f"Backup log failed: {e}")

# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(msg):
    for attempt in range(3):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={
                    "chat_id":    CHAT_ID,
                    "text":       msg,
                    "parse_mode": "Markdown"
                },
                timeout=8
            )
            if r.status_code != 200:
                log.error(
                    f"Telegram HTTP Error {r.status_code} | "
                    f"Response: {r.text}"
                )
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
    return datetime.now(timezone.utc).weekday() >= 5

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
# DUPLICATE SIGNAL FILTER
# ============================================================
def duplicate_signal(symbol_key, direction):
    now = time.time()

    duplicate_windows = {
        "XAU/USD":   3600,
        "NAS100":    5400,
        "DE30":      10800,
        "US30":      5400,
        "NIFTY50":   5400,
        "BANKNIFTY": 5400,
    }

    cooldown = duplicate_windows.get(symbol_key, 5400)

    if (
        _last_signal_direction.get(symbol_key) == direction
        and now - _last_signal_time.get(symbol_key, 0) < cooldown
    ):
        remaining = int(cooldown - (now - _last_signal_time.get(symbol_key, 0)))
        log.info(f"Duplicate signal blocked for {symbol_key} ({remaining}s remaining)")
        return True

    _last_signal_direction[symbol_key] = direction
    _last_signal_time[symbol_key]      = now
    return False

def economic_news_block():
    return False

# ============================================================
# SYMBOL-SPECIFIC SCAN DELAY
# ============================================================
def get_scan_delay(symbol_key):
    delays = {"XAU/USD": 3, "NAS100": 5, "DE30": 5, "US30": 5, "NIFTY50": 5, "BANKNIFTY": 5}
    return delays.get(symbol_key, 5)

# ============================================================
# SESSION FILTER
# ============================================================
def in_session(symbol_key):
    h = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]

    if not (s <= h < e):
        return False, "Closed"

    if symbol_key in ("NIFTY50", "BANKNIFTY"):
        return True, "India"

    if h < 7:
        return False, "Asian"

    if 7 <= h < 12:
        return True, "London"

    if 13 <= h < 15:
        return True, "NY Killzone"

    if 12 <= h < 16:
        return True, "NY+London"

    return False, "Closed"

# ============================================================
# DATA FETCHING
# ============================================================
def fetch_yf(ticker, period="15d", interval="5m"):
    try:
        raw = yf.download(
            ticker, period=period, interval=interval,
            progress=False, auto_adjust=True
        )
        if raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [str(c).lower() for c in raw.columns]
        return raw[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
    except:
        return None

def get_entry_data(symbol_key):
    yf_sym = MARKETS[symbol_key]["yf"]

    if yf_sym:
        df = fetch_yf(yf_sym)

        if df is None:
            log.error(f"{symbol_key} data fetch failed")
            return None, None

        if len(df) > 100:
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

    df["ema9"]   = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"]  = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"]  = ta.trend.EMAIndicator(cl, 50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(cl, 200).ema_indicator()
    df["rsi"]    = ta.momentum.RSIIndicator(cl, 14).rsi()
    df["atr"]    = ta.volatility.AverageTrueRange(hi, lo, cl, 14).average_true_range()
    df["adx"]    = ta.trend.ADXIndicator(hi, lo, cl, 14).adx()
    df["volma"]  = vol.rolling(20).mean()
    df["vwap"]   = (cl * vol).cumsum() / vol.cumsum()

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
    if (
        last["ema21"]
        >
        last["ema50"]
        >
        last["ema200"]
    ):
        trend = "BULL"
    elif (
        last["ema21"]
        <
        last["ema50"]
        <
        last["ema200"]
    ):
        trend = "BEAR"
    else:
        trend = MARKETS[symbol_key].get("bias", "NEUTRAL")
    cache["trend"] = trend
    cache["ts"]    = now
    return trend

# ============================================================
# PATTERN DETECTION
# ============================================================

def detect_mss(df):
    if len(df) < 12:
        return False, False

    swing_high = float(df["high"].iloc[-10:-2].max())
    swing_low  = float(df["low"].iloc[-10:-2].min())

    close = float(df.iloc[-1]["close"])

    bullish = close > swing_high
    bearish = close < swing_low

    return bullish, bearish


def confirmation_candle(df, direction):
    candle = df.iloc[-1]

    o = float(candle["open"])
    c = float(candle["close"])
    h = float(candle["high"])
    l = float(candle["low"])

    rng = h - l

    if rng <= 0:
        return False

    body = abs(c - o)

    if direction == "BUY":
        return (
            c > o
            and body / rng > 0.60
        )

    if direction == "SELL":
        return (
            c < o
            and body / rng > 0.60
        )

    return False


# ============================================================
# INSTITUTIONAL CANDLE STRUCTURE ENGINE
# ============================================================
def detect_liquidity_sweep(df, symbol_key):
    lookback  = MARKET_STRUCTURE[symbol_key]["sweep_lookback"]
    if len(df) < lookback:
        return False, False
    recent    = df.tail(lookback)
    prev_high = float(recent["high"].iloc[:-1].max())
    prev_low  = float(recent["low"].iloc[:-1].min())
    last      = recent.iloc[-1]
    bullish_sweep = (
        float(last["low"]) < prev_low
        and float(last["close"]) > prev_low
    )
    bearish_sweep = (
        float(last["high"]) > prev_high
        and float(last["close"]) < prev_high
    )
    return bullish_sweep, bearish_sweep

def detect_zone_retest(df, symbol_key, direction):
    lookback = MARKET_STRUCTURE[symbol_key]["zone_lookback"]
    if len(df) < lookback:
        return False
    recent  = df.tail(lookback)
    current = df.iloc[-1]
    if direction == "BUY":
        demand_zone = float(recent["low"].min())
        return float(current["low"]) <= demand_zone * 1.002
    if direction == "SELL":
        supply_zone = float(recent["high"].max())
        return float(current["high"]) >= supply_zone * 0.998
    return False

def detect_displacement(df, symbol_key):
    if len(df) < 2:
        return False
    mult   = MARKET_STRUCTURE[symbol_key]["displacement_mult"]
    candle = df.iloc[-1]
    body   = abs(float(candle["close"]) - float(candle["open"]))
    atr    = float(candle["atr"])
    return body > atr * mult

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
    upper_wick     = high_price - max(open_price, close_price)
    lower_wick     = min(open_price, close_price) - low_price
    wick_ratio     = MARKETS[symbol_key]["wick_ratio"]
    bullish_reject = lower_wick > body * wick_ratio
    bearish_reject = upper_wick > body * wick_ratio
    return bullish_reject, bearish_reject

def premium_discount(df, symbol_key):
    lookback = MARKET_STRUCTURE[symbol_key]["premium_discount_lookback"]
    if len(df) < lookback:
        return {"discount": False, "premium": False}
    recent      = df.tail(lookback)
    recent_high = float(recent["high"].max())
    recent_low  = float(recent["low"].min())
    midpoint    = (recent_high + recent_low) / 2
    price       = float(df.iloc[-1]["close"])
    return {"discount": price < midpoint, "premium": price > midpoint}

def institutional_structure_score(df, symbol_key):
    bull_sweep,  bear_sweep  = detect_liquidity_sweep(df, symbol_key)
    bull_wick,   bear_wick   = detect_wick_rejection(df, float(df.iloc[-1]["atr"]), symbol_key)
    displacement              = detect_displacement(df, symbol_key)
    pd_zone                   = premium_discount(df, symbol_key)

    buy_score       = 0
    sell_score      = 0
    buy_conditions  = {}
    sell_conditions = {}

    if bull_sweep:
        buy_score += 2
        buy_conditions["SWEEP"] = True
    if bull_wick:
        buy_score += 2
        buy_conditions["WICK"] = True
    if detect_zone_retest(df, symbol_key, "BUY"):
        buy_score += 2
        buy_conditions["ZONE"] = True
    if displacement:
        buy_score += 2
        buy_conditions["DISPLACEMENT"] = True
    if pd_zone["discount"]:
        buy_score += 1
        buy_conditions["DISCOUNT"] = True

    if bear_sweep:
        sell_score += 2
        sell_conditions["SWEEP"] = True
    if bear_wick:
        sell_score += 2
        sell_conditions["WICK"] = True
    if detect_zone_retest(df, symbol_key, "SELL"):
        sell_score += 2
        sell_conditions["ZONE"] = True
    if displacement:
        sell_score += 2
        sell_conditions["DISPLACEMENT"] = True
    if pd_zone["premium"]:
        sell_score += 1
        sell_conditions["PREMIUM"] = True

    if buy_score >= 8:
        buy_score += 1

    if sell_score >= 8:
        sell_score += 1

    return buy_conditions, sell_conditions, buy_score, sell_score

# ============================================================
# SUPPLY / DEMAND ZONE DETECTION
# ============================================================
def detect_supply_demand_zones(df):
    if len(df) < 20:
        return None, None
    recent = df.tail(20)
    supply = recent["high"].rolling(5).max().iloc[-1]
    demand = recent["low"].rolling(5).min().iloc[-1]
    return demand, supply

# ============================================================
# ADAPTIVE MARKET MODE
# ============================================================
def adaptive_market_mode(df):
    adx = float(df.iloc[-1]["adx"])

    if adx >= 28:
        return "TREND"

    if adx <= 18:
        return "RANGE"

    return "REVERSAL"

# ============================================================
# ADAPTIVE SCORE ENGINE
# ============================================================
def adaptive_score(
    trend,
    ema,
    vwap,
    volume,
    sweep,
    mss,
    confirm
):
    score = 0

    if trend:
        score += 20

    if ema:
        score += 15

    if vwap:
        score += 15

    if volume:
        score += 15

    if sweep:
        score += 15

    if mss:
        score += 10

    if confirm:
        score += 10

    return score

# ============================================================
# SIGNAL COUNTER
# ============================================================
def get_signal_number(symbol_key, session):
    global _signal_counter

    if _signal_counter[symbol_key]["session"] != session:
        _signal_counter[symbol_key]["session"] = session
        _signal_counter[symbol_key]["count"]   = 1
    else:
        _signal_counter[symbol_key]["count"] += 1

    signal_num = _signal_counter[symbol_key]["count"]

    if signal_num == 1:
        entry_type = "PRIMARY BREAKOUT"
    elif signal_num == 2:
        entry_type = "SECONDARY RETEST"
    else:
        entry_type = "ADVANCED CONTINUATION"

    return signal_num, entry_type

# ============================================================
# LEVELS
# ============================================================
def calc_levels(price, atr, symbol_key, df, direction, mode):
    min_sl   = MARKETS[symbol_key]["min_sl"]
    decimals = MARKETS[symbol_key]["decimals"]
    recent   = df.tail(8)

    if direction == "BUY":
        swing_dist = price - float(recent["low"].min())
    else:
        swing_dist = float(recent["high"].max()) - price

    atr_sl  = atr * ATR_MULT * ATR_MARKET_MULTIPLIER[symbol_key]
    sl_dist = max(
        min_sl,
        min(
            max(atr_sl, swing_dist * 0.85),
            swing_dist * 1.15
        )
    )

    if symbol_key == "DE30":
        if mode == "TREND":
            sl_dist *= 1.35
        else:
            sl_dist *= 1.25

    rr = MARKETS[symbol_key]["rr"]

    if symbol_key == "DE30" and mode == "TREND":
        rr += 0.2

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
def lot_for_risk(price, sl, symbol_key, risk=50):
    sl_dist = abs(price - sl)
    if sl_dist <= 0:
        return 0.01
    lot = risk / (sl_dist * DOLLAR_PER_POINT[symbol_key])
    caps = {
        "XAU/USD":   1.50,
        "NAS100":    2.00,
        "DE30":      1.50,
        "US30":      1.50,
        "NIFTY50":   1.50,
        "BANKNIFTY": 1.50,
    }
    return round(max(0.01, min(lot, caps[symbol_key])), 3)

# ============================================================
# PROCESS SYMBOL
# ============================================================
def process_symbol(symbol_key):
    log.info(f"Scanning {symbol_key}")

    if weekend_block(symbol_key):
        return
    if daily_loss_lock():
        return
    if loss_streak_lock():
        return

    watchdog()
    rotate_log()

    ok, session = in_session(symbol_key)
    if not ok:
        return

    if session not in LONDON_NY_ONLY:
        log.info(f"REJECTED {symbol_key} outside curated session ({session})")
        return

    if economic_news_block():
        log.info(f"BLOCKED {symbol_key} news window")
        return

    df, source = get_entry_data(symbol_key)
    if df is None or len(df) < 100:
        return

    spread = get_spread(df)
    if spread > MAX_SPREAD[symbol_key] * 0.90:
        log.info(f"REJECTED {symbol_key} spread {spread:.4f}")
        return

    df = add_ind(df)

    if df is None or len(df) < 50:
        log.info(f"REJECTED {symbol_key} insufficient cleaned data")
        return

    price = float(df.iloc[-1]["close"])
    atr   = float(df.iloc[-1]["atr"])

    if price <= 0:
        log.info(f"REJECTED {symbol_key} invalid price")
        return

    demand_zone, supply_zone = detect_supply_demand_zones(df)

    planned_entry = float(df.iloc[-2]["close"])

    if symbol_key == "XAU/USD":
        max_entry_drift = atr * 0.25
    elif symbol_key == "DE30":
        max_entry_drift = atr * 0.30
    else:
        max_entry_drift = atr * 0.35

    if not (MARKETS[symbol_key]["price_lo"] <= price <= MARKETS[symbol_key]["price_hi"]):
        log.info(f"REJECTED {symbol_key} price out of range")
        return

    trend = get_trend(symbol_key)

    mode = adaptive_market_mode(df)

    last = df.iloc[-1]

    vwap_buy  = float(last["close"]) > float(last["vwap"])
    vwap_sell = float(last["close"]) < float(last["vwap"])

    relative_volume = (
        float(last["volume"])
        >
        float(last["volma"]) * 1.20
    )

    ema_buy = float(last["ema50"]) > float(last["ema200"])

    ema_sell = float(last["ema50"]) < float(last["ema200"])

    bull_sweep, bear_sweep = detect_liquidity_sweep(df, symbol_key)

    bull_mss, bear_mss = detect_mss(df)

    bull_confirm = confirmation_candle(df, "BUY")

    bear_confirm = confirmation_candle(df, "SELL")

    buy_signal  = False
    sell_signal = False
    best        = 0

    rsi = float(df.iloc[-1]["rsi"])
    adx = float(df.iloc[-1]["adx"])
    dec = MARKETS[symbol_key]["decimals"]

    log.info(
        f"{symbol_key} | Mode: {mode} | Trend: {trend} | Session: {session}"
    )

    # --------------------------------------------------------
    # TREND MODE
    # --------------------------------------------------------
    if mode == "TREND":

        buy_signal = (
            trend == "BULL"
            and ema_buy
            and vwap_buy
            and relative_volume
            and bull_sweep
            and bull_mss
            and bull_confirm
        )

        sell_signal = (
            trend == "BEAR"
            and ema_sell
            and vwap_sell
            and relative_volume
            and bear_sweep
            and bear_mss
            and bear_confirm
        )

    # --------------------------------------------------------
    # REVERSAL MODE — skip
    # --------------------------------------------------------
    elif mode == "REVERSAL":
        return

    # --------------------------------------------------------
    # RANGE MODE — skip
    # --------------------------------------------------------
    else:
        log.info(f"REJECTED {symbol_key} RANGE")
        return

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------
    if buy_signal:
        direction = "BUY"
    elif sell_signal:
        direction = "SELL"
    else:
        return

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------
    if direction == "BUY":
        best = adaptive_score(
            trend == "BULL",
            ema_buy,
            vwap_buy,
            relative_volume,
            bull_sweep,
            bull_mss,
            bull_confirm
        )
    else:
        best = adaptive_score(
            trend == "BEAR",
            ema_sell,
            vwap_sell,
            relative_volume,
            bear_sweep,
            bear_mss,
            bear_confirm
        )

    # --------------------------------------------------------
    # MINIMUM SCORE FILTER
    # --------------------------------------------------------
    if best < 90:
        log.info(f"REJECTED {symbol_key} score {best}")
        return

    if direction == "SELL" and supply_zone:
        if price < supply_zone * 0.998:
            log.info(f"REJECTED {symbol_key} weak supply rejection")
            return

    if direction == "BUY" and demand_zone:
        if price > demand_zone * 1.002:
            log.info(f"REJECTED {symbol_key} weak demand rejection")
            return

    if direction == "SELL":
        if price < planned_entry - max_entry_drift:
            log.info(f"REJECTED {symbol_key} late SELL drift")
            return

    if direction == "BUY":
        if price > planned_entry + max_entry_drift:
            log.info(f"REJECTED {symbol_key} late BUY drift")
            return

    if duplicate_signal(symbol_key, direction):
        return

    now = time.time()
    if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
        remaining = int(SIGNAL_COOLDOWN - (now - _signal_sent[symbol_key]))
        log.info(f"REJECTED {symbol_key} cooldown {remaining}s")
        return

    _signal_sent[symbol_key] = now

    if direction == "BUY":
        price += EXECUTION_BUFFER[symbol_key]
    else:
        price -= EXECUTION_BUFFER[symbol_key]

    sl, tp, sl_dist, rr = calc_levels(price, atr, symbol_key, df, direction, mode)
    lot                  = lot_for_risk(price, sl, symbol_key)
    timeframe            = MODE_TIMEFRAME.get(mode, "1H / 4H")
    signal_type          = "CONTINUATION"
    signal_num, entry_type = get_signal_number(symbol_key, session)

    log_signal(symbol_key, direction, best, rr, price, sl, tp,
               session, mode, timeframe, signal_type)
    sync_real_pnl()

    cond_lines = []
    if direction == "BUY":
        if trend == "BULL":    cond_lines.append(" HTF_BULL")
        if ema_buy:            cond_lines.append(" EMA50 > EMA200")
        if vwap_buy:           cond_lines.append(" VWAP_BUY")
        if relative_volume:    cond_lines.append(" REL_VOLUME")
        if bull_sweep:         cond_lines.append(" LIQUIDITY_SWEEP")
        if bull_mss:           cond_lines.append(" MSS")
        if bull_confirm:       cond_lines.append(" CONFIRMATION_CANDLE")
    else:
        if trend == "BEAR":    cond_lines.append(" HTF_BEAR")
        if ema_sell:           cond_lines.append(" EMA50 < EMA200")
        if vwap_sell:          cond_lines.append(" VWAP_SELL")
        if relative_volume:    cond_lines.append(" REL_VOLUME")
        if bear_sweep:         cond_lines.append(" LIQUIDITY_SWEEP")
        if bear_mss:           cond_lines.append(" MSS")
        if bear_confirm:       cond_lines.append(" CONFIRMATION_CANDLE")

    if demand_zone:
        cond_lines.append(" DEMAND_ZONE")
    if supply_zone:
        cond_lines.append(" SUPPLY_ZONE")

    cond_text    = "\n".join(cond_lines)
    action_emoji = "📈" if direction == "BUY" else "📉"

    msg = (
        f"🎯 *{SYSTEM_VERSION}* | INSTITUTIONAL EXECUTION\n"
        f"*{MARKETS[symbol_key]['mt5']}* | ⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n\n"
        f"🔥 *Action:* {direction} {action_emoji}\n"
        f"🎯 *Signal #:* {signal_num}\n"
        f"📍 *Entry Type:* {entry_type}\n"
        f"🚀 *Signal Type:* CONTINUATION\n"
        f"⭐ *Score:* {best}\n"
        f"🧠 *Mode:* {mode}\n"
        f"⏱ *Timeframe:* {timeframe}\n"
        f"📊 *Market Bias:* {MARKETS[symbol_key]['bias']}\n\n"
        f"📍 *Entry:* {price:,.{dec}f}\n"
        f"🛑 *SL:* {sl:,.{dec}f}\n"
        f"🎯 *TP:* {tp:,.{dec}f} *(1:{rr} RR)*\n\n"
        f"📈 *RSI:* {rsi:.1f}\n"
        f"📉 *ADX:* {adx:.1f}\n"
        f"🌍 *Trend:* {trend}\n"
        f"⏰ *Session:* {session}\n"
        f"📡 *Source:* {source}\n\n"
        f"💵 *Lot:* {lot}\n\n"
        f"✅ *Conditions:*\n"
        f"{cond_text}\n\n"
        f"🛡 *ELITE INSTITUTIONAL FILTER ACTIVE*\n"
        f"⚡ *GLOBAL ELITE INSTITUTIONAL MODE*"
    )

    send_telegram(msg)

    log.info(
        f"SIGNAL SENT {symbol_key} {direction} | "
        f"Entry: {price} | SL: {sl} | TP: {tp} | "
        f"RR: {rr} | Type: CONTINUATION | Signal#: {signal_num} | "
        f"EntryType: {entry_type} | Mode: {mode} | TF: {timeframe}"
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
        f"🇺🇸 US30\n"
        f"🇮🇳 NIFTY50\n"
        f"🏦 BANKNIFTY\n\n"
        f"🚀 Pure Continuation Engine Active\n"
        f"🛡 Curated Institutional Entry Active\n"
        f"⚡ Global Elite Pro+ Curated Mode"
    )

    while True:
        try:
            reset_daily()

            with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
                futures = []
                for symbol in SYMBOLS:
                    futures.append(
                        executor.submit(process_symbol, symbol)
                    )
                    time.sleep(0.15)

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        log.error(f"Thread error: {e}")

            time.sleep(MAIN_LOOP_DELAY)

        except Exception as e:
            log.error(f"Main loop error: {e}")
            time.sleep(MAIN_LOOP_DELAY)

if __name__ == "__main__":
    main()
