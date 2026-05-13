# ============================================================
# PEPPERSTONE MOMENTUM HUNTER v22.0-INSTITUTIONAL-HEDGEFUND-ULTRA+
# GOLD + NAS100 + DE30 + US30
# CONTINUATION + REVERSAL | INSTITUTIONAL PRECISION ENGINE
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

SYSTEM_VERSION = "v22.0-INSTITUTIONAL-HEDGEFUND-ULTRA+"  # PATCH 1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v21-curated")

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
        "rr":         2.8,
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
        "rr":         2.7,
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
        "rr":         2.8,
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
        "rr":         2.6,
        "sweep_bonus": 2,
        "wick_ratio": 1.5,
    },
}

SYMBOLS = ["XAU/USD", "NAS100", "DE30", "US30"]

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
MAIN_LOOP_DELAY        = 2  # PATCH 5

STDV_PERIOD           = 20
STDV_THRESHOLD_MULT   = 1.15
AOX_FAST              = 5
AOX_SLOW              = 34
ASIA_ELITE_SESSION    = [0, 3]   # Gold only

# ============================================================
# EXECUTION SLIPPAGE BUFFER
# ============================================================
EXECUTION_BUFFER = {
    "XAU/USD": 0.20,
    "NAS100":  2.5,   # PATCH 15
    "DE30":    3.0,
    "US30":    2.5,   # PATCH 15
}

# ============================================================
# SCORE THRESHOLDS BY REGIME
# ============================================================
RANGE_MIN_SCORE    = 5
TREND_MIN_SCORE    = 6
REVERSAL_MIN_SCORE = 6

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
}

# ============================================================
# MARKET-SPECIFIC STRUCTURE SCORE FILTERS
# ============================================================
MARKET_MIN_STRUCTURE_SCORE = {
    "XAU/USD": 7,
    "NAS100":  8,
    "DE30":    7,
    "US30":    8,  # PATCH 18
}

# ============================================================
# REVERSAL SETTINGS
# ============================================================
REVERSAL_RSI_OVERBOUGHT = {
    "XAU/USD": 72,
    "NAS100":  78,
    "DE30":    76,
    "US30":    75,
}

REVERSAL_RSI_OVERSOLD = {
    "XAU/USD": 31,
    "NAS100":  25,
    "DE30":    27,
    "US30":    28,
}

REVERSAL_ADX_MIN     = 25
REVERSAL_SCORE_BONUS = 2

# ============================================================
# SESSION CURATION
# ============================================================
LONDON_NY_ONLY = [
    "Asia Elite",
    "London",
    "NY+London",
    "NY Killzone"  # PATCH 3
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

# ============================================================
# DOLLAR PER POINT
# ============================================================
DOLLAR_PER_POINT = {
    "XAU/USD": 100,
    "NAS100":  10,
    "DE30":    10,
    "US30":    10,
}

# ============================================================
# MAX SPREAD
# ============================================================
MAX_SPREAD = {
    "XAU/USD": 1.20,
    "NAS100":  4.0,
    "DE30":    5.0,
    "US30":    6.0,
}

# ============================================================
# REGIME TO TIMEFRAME MAP
# ============================================================
REGIME_TIMEFRAME = {
    "SCALP":    "1M / 5M",
    "RANGE":    "15M / 30M",
    "TREND":    "1H / 4H",
    "BREAKOUT": "15M / 1H",
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
                f"{SYSTEM_VERSION} | ACTIVE"  # PATCH 8
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
               session, regime, timeframe, signal_type):
    file_exists = os.path.isfile("signals_log.csv")
    with open("signals_log.csv", "a", newline="") as f:
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
        with open("signals_backup.csv", "a", newline="") as backup:
            backup_writer = csv.writer(backup)
            backup_writer.writerow([
                SYSTEM_VERSION,
                datetime.now(timezone.utc).isoformat(),
                symbol, direction, score, rr,
                entry, sl, tp, session,
                regime, timeframe, signal_type
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
                timeout=8  # PATCH 2
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
        "XAU/USD": 3600,
        "NAS100":  5400,
        "DE30":    10800,
        "US30":    5400,
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
    delays = {"XAU/USD": 3, "NAS100": 5, "DE30": 5, "US30": 5}
    return delays.get(symbol_key, 5)

# ============================================================
# SESSION FILTER
# ============================================================
def in_session(symbol_key):
    h = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]

    if symbol_key == "XAU/USD":
        if ASIA_ELITE_SESSION[0] <= h < ASIA_ELITE_SESSION[1]:
            return True, "Asia Elite"

    if not (s <= h < e):
        return False, "Closed"

    if h < 7:
        return False, "Asian"

    if 13 <= h < 15:          # PATCH 4 — NY Killzone (checked before NY+London)
        return True, "NY Killzone"

    if 12 <= h < 16:
        return True, "NY+London"

    if 7 <= h < 12:
        return True, "London"

    return False, "NY"

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

# PATCH 7 — yfinance failure logging
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

    # PATCH 12 — Perfect structure bonus
    if buy_score >= 8:
        buy_score += 1

    if sell_score >= 8:
        sell_score += 1

    return buy_conditions, sell_conditions, buy_score, sell_score

# ============================================================
# SUPPLY / DEMAND ZONE DETECTION
# ============================================================
def detect_supply_demand_zones(df):
    """Institutional supply/demand zone detection for rejection block entries."""
    if len(df) < 20:
        return None, None
    recent = df.tail(20)
    supply = recent["high"].rolling(5).max().iloc[-1]
    demand = recent["low"].rolling(5).min().iloc[-1]
    return demand, supply

# ============================================================
# ELITE REVERSAL DETECTION
# ============================================================
def detect_reversal(df, symbol_key):
    """Elite institutional reversal detection."""
    if len(df) < 5:
        return False, False
    last       = df.iloc[-1]
    prev       = df.iloc[-2]
    rsi        = float(last["rsi"])
    adx        = float(last["adx"])
    high_break = float(last["high"]) > float(prev["high"])
    low_break  = float(last["low"])  < float(prev["low"])
    close      = float(last["close"])
    prev_close = float(prev["close"])
    bull_sweep, bear_sweep = detect_liquidity_sweep(df, symbol_key)
    bearish_reversal = (
        rsi >= REVERSAL_RSI_OVERBOUGHT[symbol_key]
        and adx >= REVERSAL_ADX_MIN
        and high_break
        and close < prev_close
        and bear_sweep
    )
    bullish_reversal = (
        rsi <= REVERSAL_RSI_OVERSOLD[symbol_key]
        and adx >= REVERSAL_ADX_MIN
        and low_break
        and close > prev_close
        and bull_sweep
    )
    return bullish_reversal, bearish_reversal

# ============================================================
# MARKET REGIME
# ============================================================
def detect_market_regime(df):
    adx = float(df.iloc[-1]["adx"])
    if adx >= 35:
        return "BREAKOUT"
    elif adx >= 25:
        return "TREND"
    else:
        return "RANGE"

# ============================================================
# BUILD SCORE
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

    stdv = float(last["stdv"]) if not pd.isna(last["stdv"]) else 0
    stdv_ma = (
        df["stdv"].rolling(STDV_PERIOD).mean().iloc[-1]
        if len(df) > STDV_PERIOD else 0
    )
    aox = float(last["aox"]) if not pd.isna(last["aox"]) else 0

    bull_fvg,   bear_fvg   = fair_value_gap(df)
    bull_choch, bear_choch = detect_choch(df)
    bull_rev,   bear_rev   = detect_reversal(df, symbol_key)
    bull_sweep, bear_sweep = detect_liquidity_sweep(df, symbol_key)
    bull_wick,  bear_wick  = detect_wick_rejection(df, atr, symbol_key)

    bullish_break = float(last["close"]) > float(df.iloc[-2]["high"]) + atr * 0.12
    bearish_break = float(last["close"]) < float(df.iloc[-2]["low"])  - atr * 0.12

    buy = {
        "HTF":      trend == "BULL",
        "EMA":      ema9 > ema21 > ema50 > ema200,
        "RSI":      56 <= rsi <= 72,
        "ADX":      adx > ADX_THRESHOLD,
        "VOL":      volma > 0 and vol > volma * VOL_MULT,
        "FVG":      bull_fvg,
        "CHOCH":    bull_choch,
        "BOS":      bullish_break,
        "REVERSAL": bull_rev,
        "SWEEP":    bull_sweep,
        "WICK":     bull_wick,
        "STDV":     stdv_ma > 0 and stdv > stdv_ma * STDV_THRESHOLD_MULT,
        "AOX":      aox > 0,
    }

    sell = {
        "HTF":      trend == "BEAR",
        "EMA":      ema9 < ema21 < ema50 < ema200,
        "RSI":      30 <= rsi <= 44,
        "ADX":      adx > ADX_THRESHOLD,
        "VOL":      volma > 0 and vol > volma * VOL_MULT,
        "FVG":      bear_fvg,
        "CHOCH":    bear_choch,
        "BOS":      bearish_break,
        "REVERSAL": bear_rev,
        "SWEEP":    bear_sweep,
        "WICK":     bear_wick,
        "STDV":     stdv_ma > 0 and stdv > stdv_ma * STDV_THRESHOLD_MULT,
        "AOX":      aox < 0,
    }

    buy_score  = sum(buy.values())
    sell_score = sum(sell.values())

    if buy["STDV"] and buy["AOX"]:
        buy_score += 1
    if sell["STDV"] and sell["AOX"]:
        sell_score += 1

    if bull_rev:
        buy_score  += REVERSAL_SCORE_BONUS
    if bear_rev:
        sell_score += REVERSAL_SCORE_BONUS

    sweep_bonus = MARKETS[symbol_key]["sweep_bonus"]
    if bull_sweep and bull_wick:
        buy_score += sweep_bonus
    if bear_sweep and bear_wick:
        sell_score += sweep_bonus

    if symbol_key == "XAU/USD":
        if bull_sweep:
            buy_score  += 1
        if bear_sweep:
            sell_score += 1
        # PATCH 17 — Gold sweep dominance wick boost
        if bull_wick:
            buy_score  += 1
        if bear_wick:
            sell_score += 1

    # PATCH 11 — ADX breakout momentum boost
    if adx >= 35:
        if buy_score > sell_score:
            buy_score += 1
        elif sell_score > buy_score:
            sell_score += 1

    return buy, sell, buy_score, sell_score

# ============================================================
# LEVELS
# ============================================================
def calc_levels(price, atr, symbol_key, df, direction, reversal_mode, regime):
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
        if regime == "BREAKOUT":
            sl_dist *= 1.35
        else:
            sl_dist *= 1.25

    rr = 2.0 if reversal_mode else MARKETS[symbol_key]["rr"]

    # PATCH 16 — DE30 breakout RR boost
    if symbol_key == "DE30" and regime == "BREAKOUT" and not reversal_mode:
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
def lot_for_risk(price, sl, symbol_key, risk=25):
    sl_dist = abs(price - sl)
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
    if spread > MAX_SPREAD[symbol_key] * 0.90:  # PATCH 9
        log.info(f"REJECTED {symbol_key} spread {spread:.4f}")
        return

    df = add_ind(df)

    if df is None or len(df) < 50:
        log.info(f"REJECTED {symbol_key} insufficient cleaned data")
        return

    price = float(df.iloc[-1]["close"])
    atr   = float(df.iloc[-1]["atr"])

    # PATCH 10 — Invalid price failsafe
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

    trend  = get_trend(symbol_key)
    regime = detect_market_regime(df)

    buy, sell, buy_score, sell_score = build_score(df, trend, symbol_key)

    structure_buy, structure_sell, structure_buy_score, structure_sell_score = (
        institutional_structure_score(df, symbol_key)
    )

    buy.update(structure_buy)
    sell.update(structure_sell)

    buy_score  += structure_buy_score
    sell_score += structure_sell_score

    rsi = float(df.iloc[-1]["rsi"])
    adx = float(df.iloc[-1]["adx"])
    dec = MARKETS[symbol_key]["decimals"]

    bull_rev = buy.get("REVERSAL", False)
    bear_rev = sell.get("REVERSAL", False)

    best      = max(buy_score, sell_score)
    direction = "BUY" if buy_score >= sell_score else "SELL"

    reversal_mode = bull_rev if direction == "BUY" else bear_rev

    log.info(
        f"{symbol_key} | BUY: {buy_score} | SELL: {sell_score} | "
        f"Regime: {regime} | Trend: {trend} | Session: {session} | "
        f"Reversal: {reversal_mode}"
    )

    if symbol_key == "DE30":
        de30_range_score = 7
        de30_trend_score = 8
    else:
        de30_range_score = RANGE_MIN_SCORE
        de30_trend_score = TREND_MIN_SCORE

    if regime == "RANGE" and best < de30_range_score:
        log.info(f"REJECTED {symbol_key} RANGE score {best} < {de30_range_score}")
        return

    if regime in ["TREND", "BREAKOUT"] and best < de30_trend_score:
        log.info(f"REJECTED {symbol_key} TREND score {best} < {de30_trend_score}")
        return

    if reversal_mode and best < REVERSAL_MIN_SCORE:
        log.info(f"REJECTED {symbol_key} reversal score {best} < {REVERSAL_MIN_SCORE}")
        return

    best_structure_score = max(structure_buy_score, structure_sell_score)
    if best_structure_score < MARKET_MIN_STRUCTURE_SCORE[symbol_key]:
        log.info(f"REJECTED {symbol_key} weak structure score {best_structure_score}")
        return

    if trend == "BULL" and direction == "SELL" and not reversal_mode:
        log.info(f"REJECTED {symbol_key} countertrend SELL without reversal")
        return

    if trend == "BEAR" and direction == "BUY" and not reversal_mode:
        log.info(f"REJECTED {symbol_key} countertrend BUY without reversal")
        return

    if direction == "SELL" and supply_zone:
        if price < supply_zone * 0.998:  # PATCH 13
            log.info(f"REJECTED {symbol_key} weak supply rejection")
            return

    if direction == "BUY" and demand_zone:
        if price > demand_zone * 1.002:  # PATCH 13
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

    sl, tp, sl_dist, rr = calc_levels(price, atr, symbol_key, df, direction, reversal_mode, regime)
    lot                  = lot_for_risk(price, sl, symbol_key)
    timeframe            = REGIME_TIMEFRAME.get(regime, "1H / 4H")
    signal_type          = "REVERSAL" if reversal_mode else "CONTINUATION"

    log_signal(symbol_key, direction, best, rr, price, sl, tp,
               session, regime, timeframe, signal_type)
    sync_real_pnl()

    checks    = buy if direction == "BUY" else sell
    cond_text = "\n".join([f" {k}" for k, v in checks.items() if v])

    if demand_zone:
        cond_text += "\n DEMAND_ZONE"
    if supply_zone:
        cond_text += "\n SUPPLY_ZONE"

    action_emoji = "📈" if direction == "BUY" else "📉"
    type_emoji   = "🔄" if reversal_mode else "🚀"

    msg = (
        f"🎯 *{SYSTEM_VERSION}* | INSTITUTIONAL EXECUTION\n"  # PATCH 19
        f"*{MARKETS[symbol_key]['mt5']}* | ⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n\n"
        f"🔥 *Action:* {direction} {action_emoji}\n"
        f"{type_emoji} *Signal Type:* {signal_type}\n"
        f"⭐ *Score:* {best}\n"  # PATCH 14
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
        f"RR: {rr} | Type: {signal_type} | Regime: {regime} | TF: {timeframe}"
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
        f"🔄 Reversal + Continuation Engine Active\n"
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
                    time.sleep(0.15)  # PATCH 6

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
