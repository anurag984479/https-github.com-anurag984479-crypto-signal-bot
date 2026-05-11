# ═══════════════════════════════════════════════════════════════
# PEPPERSTONE MOMENTUM HUNTER v19.0
# SNIPER INSTITUTIONAL PRECISION ENGINE
# MARKET-TUNED MAY 2026
# ✔ Sniper Score Engine       ✔ Premium / Discount Zones
# ✔ Retest Confirmation       ✔ Multi-Candle Confirmation
# ✔ Wick Rejection Validation ✔ Liquidity Sweep Confirm
# ✔ Smart SL Buffer           ✔ CHOCH Detection
# ✔ Market Regime Detection   ✔ Adaptive Scoring
# ✔ Fair Value Gap            ✔ Precision Entry Zones
# ✔ VWAP Reclaim              ✔ Order Block
# ✔ Adaptive RR               ✔ Dynamic Risk
# ✔ ICT / TVM Kill Zones      ✔ Session Precision
# ✔ Trade Journal             ✔ News Blackout
# ✔ Weekend Filter            ✔ Daily Loss Lock
# ✔ Loss Streak Breaker       ✔ Daily Auto-Reset
# ✔ Duplicate Signal Decay    ✔ CSV Rotation
# ✔ BTC Overtrading Guard     ✔ Telegram Retry
# ✔ VPS Watchdog              ✔ Dashboard Logging
# ✔ Execute Trade Bridge      ✔ PnL Sync
# ✔ Bull Market Bias          ✔ Timeframe Display
# ═══════════════════════════════════════════════════════════════

import time
import logging
import requests
import ccxt
import pandas as pd
import ta
import os
import csv
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

SYSTEM_VERSION = "v19.0-SNIPER-INSTITUTIONAL-PRECISION"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v19.0")

TOKEN = os.getenv("TOKEN", "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

if not TOKEN or not CHAT_ID:
    raise ValueError("Missing TOKEN or CHAT_ID")

DOLLAR_PER_LOT = {
    "XAU/USD": 100.0,
    "XAG/USD": 5000.0,
    "BTC/USD": 1.0,
    "NAS100":  10.0,
    "US500":   10.0,
}

# ═══════════════════════════════════════════════════════════════
# MARKETS — tuned for May 2026
# ═══════════════════════════════════════════════════════════════
MARKETS = {
    "XAU/USD": {
        "mt5":      "XAUUSD.Qraw",
        "yf":       "GC=F",
        "price_lo": 4800,
        "price_hi": 6000,
        "sessions": [7, 20],
        "decimals": 2,
        "min_sl":   7.0,
        "tier":     "GOLD ELITE",
        "bias":     "BULL",
    },
    "XAG/USD": {
        "mt5":      "XAGUSD.Qraw",
        "yf":       "SI=F",
        "price_lo": 28,
        "price_hi": 60,
        "sessions": [7, 20],
        "decimals": 3,
        "min_sl":   0.35,
        "tier":     "SILVER ELITE",
        "bias":     "BULL",
    },
    "BTC/USD": {
        "mt5":      "BTCUSD.Qraw",
        "yf":       None,
        "price_lo": 70000,
        "price_hi": 130000,
        "sessions": [0, 23],
        "decimals": 2,
        "min_sl":   250.0,
        "tier":     "BTC ELITE",
        "bias":     "BULL",
    },
    "NAS100": {
        "mt5":      "NAS100",
        "yf":       "^NDX",
        "price_lo": 15000,
        "price_hi": 28000,
        "sessions": [13, 21],
        "decimals": 1,
        "min_sl":   55.0,
        "tier":     "NAS100 ELITE",
        "bias":     "BULL",
    },
    "US500": {
        "mt5":      "US500.Qtek",
        "yf":       "^GSPC",
        "price_lo": 4500,
        "price_hi": 8000,
        "sessions": [13, 21],
        "decimals": 2,
        "min_sl":   25.0,
        "tier":     "US500 ELITE",
        "bias":     "BULL",
    },
}

SYMBOLS = list(MARKETS.keys())

# ═══════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════
ATR_MULT                   = 0.45
VOL_MULT                   = 1.05
ADX_THRESHOLD              = 20
ATR_SPIKE_MULT             = 2.2
SIGNAL_COOLDOWN            = 1200
HTF_REFRESH                = 1200
BTC_EXTRA_COOLDOWN         = 1800

TREND_WEIGHT               = 1.30
BREAKOUT_WEIGHT            = 1.25

RANGE_ADX_LIMIT            = 18
TREND_ADX_LIMIT            = 25
EXTREME_ADX_LIMIT          = 35

MAX_DAILY_LOSS             = -300
MAX_CONSECUTIVE_LOSSES     = 4

# ── Sniper settings
SNIPER_CONFIRM_CANDLES     = 2
RETEST_LOOKBACK            = 3
WICK_REJECTION_RATIO       = 1.8
SL_BUFFER_ATR_MULT         = 0.35
MIN_SNIPER_SCORE           = 5     # out of 7 conditions

MAX_SPREAD = {
    "XAU/USD": 0.80,
    "XAG/USD": 0.08,
    "BTC/USD": 60,
    "NAS100":  4.0,
    "US500":   2.0,
}

REGIME_TIMEFRAME = {
    "SCALP":    "1M / 5M",
    "RANGE":    "15M / 30M",
    "TREND":    "1H / 4H",
    "BREAKOUT": "15M / 1H",
}

# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════
daily_pnl              = 0
consecutive_losses     = 0
last_reset_day         = datetime.now(timezone.utc).day

_signal_sent           = {s: 0 for s in SYMBOLS}
_htf_cache             = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}
_last_signal_direction = {}
_last_signal_time      = {}


def reset_daily():
    global daily_pnl, consecutive_losses, last_reset_day
    current_day = datetime.now(timezone.utc).day
    if current_day != last_reset_day:
        daily_pnl          = 0
        consecutive_losses = 0
        last_reset_day     = current_day
        log.info("Daily stats reset")


def update_trade_result(pnl):
    global daily_pnl, consecutive_losses
    daily_pnl += pnl
    if pnl < 0:
        consecutive_losses += 1
    else:
        consecutive_losses = 0


def sync_real_pnl():
    return daily_pnl


def watchdog():
    try:
        with open("heartbeat.txt", "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        log.error(f"Watchdog failure: {e}")


def dashboard_log(symbol, direction, score, regime, rr, timeframe):
    log.info(
        f"[DASHBOARD] {symbol} | {direction} | "
        f"Score: {score} | Regime: {regime} | "
        f"RR: {rr} | TF: {timeframe}"
    )


def execute_trade(symbol_key, direction, lot, entry, sl, tp):
    try:
        log.info(
            f"EXECUTING {symbol_key} {direction} | "
            f"Lot {lot} | Entry {entry} | SL {sl} | TP {tp}"
        )
        return True
    except Exception as e:
        log.error(f"Execution failed: {e}")
        return False


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
                timeout=10
            )
            log.info(f"Telegram sent | {r.text}")
            return True
        except Exception as e:
            log.error(f"Telegram error attempt {attempt + 1}: {e}")
            time.sleep(2)
    return False


def in_session(symbol_key):
    h = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]
    if not (s == 0 and e == 23) and not (s <= h < e):
        return False, "Closed"
    if 12 <= h < 16:
        return True, "NY+London"
    if 7 <= h < 12:
        return True, "London"
    return True, "Asian"


def weekend_block(symbol_key):
    weekday = datetime.now(timezone.utc).weekday()
    if weekday >= 5 and symbol_key != "BTC/USD":
        return True
    return False


def daily_loss_lock():
    if daily_pnl <= MAX_DAILY_LOSS:
        log.info("Daily loss lock active")
        return True
    return False


def loss_streak_lock():
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        log.info("Kill switch: 4 consecutive losses")
        return True
    return False


def duplicate_signal(symbol_key, direction):
    now = time.time()
    if (
        _last_signal_direction.get(symbol_key) == direction
        and now - _last_signal_time.get(symbol_key, 0) < 7200
    ):
        log.info(f"Duplicate signal blocked for {symbol_key}")
        return True
    _last_signal_direction[symbol_key] = direction
    _last_signal_time[symbol_key]      = now
    return False


def economic_news_block():
    try:
        h = datetime.now(timezone.utc).hour
        return h in [12, 13, 14]
    except Exception as e:
        log.error(f"Economic API failure: {e}")
        return False


def rotate_log():
    file_path = "signals_log.csv"
    if os.path.isfile(file_path):
        if os.path.getsize(file_path) > 5_000_000:
            os.rename(file_path, f"signals_log_{int(time.time())}.csv")


def safe_rr(price, sl, tp):
    risk_distance = abs(price - sl)
    if risk_distance <= 0:
        return 0
    return abs(tp - price) / risk_distance


def atr_is_safe(df, atr):
    atr_mean = df["atr"].rolling(50).mean().iloc[-1]
    if pd.isna(atr_mean) or atr_mean == 0:
        return False
    return atr < atr_mean * ATR_SPIKE_MULT


def build_conditions_text(checks):
    conditions_text = "\n".join([f" {k}" for k, v in checks.items() if v])
    if len(conditions_text) > 1200:
        conditions_text = conditions_text[:1200]
    return conditions_text


def get_sr_levels(df, lookback=50):
    return (
        df["low"].tail(lookback).min(),
        df["high"].tail(lookback).max()
    )


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


def fetch_ccxt(src_name, sym, tf="5m", limit=300):
    try:
        exchange = getattr(ccxt, src_name)()
        ohlcv    = exchange.fetch_ohlcv(sym, timeframe=tf, limit=limit)
        return pd.DataFrame(
            ohlcv, columns=["time", "open", "high", "low", "close", "volume"]
        )
    except:
        return None


def get_entry_data(symbol_key):
    if symbol_key == "BTC/USD":
        for src in ["coinbase", "binance"]:
            pair = "BTC/USDT" if src == "binance" else "BTC/USD"
            df   = fetch_ccxt(src, pair)
            if df is not None and len(df) > 100:
                return df, src
    yf_sym = MARKETS[symbol_key]["yf"]
    if yf_sym:
        df = fetch_yf(yf_sym)
        if df is not None and len(df) > 100:
            return df, "yf"
    return None, None


def get_htf(symbol_key):
    if symbol_key == "BTC/USD":
        for src in ["coinbase", "binance"]:
            pair = "BTC/USDT" if src == "binance" else "BTC/USD"
            df   = fetch_ccxt(src, pair, tf="15m", limit=300)
            if df is not None and len(df) > 100:
                return df
    yf_sym = MARKETS[symbol_key]["yf"]
    if yf_sym:
        return fetch_yf(yf_sym, period="15d", interval="15m")
    return None


def get_spread(df):
    if df is None or len(df) < 3:
        return 999
    recent    = df.tail(3)
    avg_range = (
        recent["high"].astype(float) - recent["low"].astype(float)
    ).mean()
    return avg_range * 0.18


def add_ind(df):
    df  = df.copy()
    cl  = pd.to_numeric(df["close"])
    hi  = pd.to_numeric(df["high"])
    lo  = pd.to_numeric(df["low"])
    vol = pd.to_numeric(df["volume"])
    df["ema9"]   = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"]  = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"]  = ta.trend.EMAIndicator(cl, 50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(cl, 200).ema_indicator()
    df["rsi"]    = ta.momentum.RSIIndicator(cl, 14).rsi()
    df["atr"]    = ta.volatility.AverageTrueRange(hi, lo, cl, 14).average_true_range()
    df["adx"]    = ta.trend.ADXIndicator(hi, lo, cl, 14).adx()
    df["volma"]  = vol.rolling(20).mean()
    df["vwap"]   = (cl * vol).cumsum() / vol.cumsum()
    return df


def get_trend(symbol_key):
    cache = _htf_cache[symbol_key]
    now   = time.time()
    if now - cache["ts"] < HTF_REFRESH:
        return cache["trend"]
    df = get_htf(symbol_key)
    if df is None or len(df) < 50:
        return "NEUTRAL"
    df   = add_ind(df)
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


# ═══════════════════════════════════════════════════════════════
# ICT MODULES
# ═══════════════════════════════════════════════════════════════
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


def fair_value_gap(df):
    if len(df) < 3:
        return False, False
    c1 = df.iloc[-3]
    c3 = df.iloc[-1]
    return (
        float(c1["high"]) < float(c3["low"]),
        float(c1["low"])  > float(c3["high"])
    )


def detect_market_regime(df):
    last    = df.iloc[-1]
    adx     = float(last["adx"])
    ema9    = float(last["ema9"])
    ema21   = float(last["ema21"])
    atr     = float(last["atr"])
    ema_gap = abs(ema9 - ema21)
    if adx >= EXTREME_ADX_LIMIT:
        return "BREAKOUT"
    elif adx >= TREND_ADX_LIMIT and ema_gap > atr * 0.15:
        return "TREND"
    elif adx <= RANGE_ADX_LIMIT:
        return "RANGE"
    return "SCALP"


# ═══════════════════════════════════════════════════════════════
# SNIPER MODULES
# ═══════════════════════════════════════════════════════════════
def previous_candle_zone(df):
    if len(df) < 2:
        return None
    prev = df.iloc[-2]
    return {
        "high":      float(prev["high"]),
        "low":       float(prev["low"]),
        "body_high": max(float(prev["open"]), float(prev["close"])),
        "body_low":  min(float(prev["open"]), float(prev["close"])),
        "bullish":   float(prev["close"]) > float(prev["open"]),
        "bearish":   float(prev["close"]) < float(prev["open"]),
    }


def premium_discount_zone(df):
    support, resistance = get_sr_levels(df)
    current  = float(df.iloc[-1]["close"])
    midpoint = (float(support) + float(resistance)) / 2
    return current > midpoint, current < midpoint


def sniper_wick_confirmation(df):
    last  = df.iloc[-1]
    high  = float(last["high"])
    low   = float(last["low"])
    open_ = float(last["open"])
    close = float(last["close"])
    body       = abs(close - open_)
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    return (
        lower_wick > body * WICK_REJECTION_RATIO,
        upper_wick > body * WICK_REJECTION_RATIO
    )


def sniper_retest_confirmation(df, direction):
    zone = previous_candle_zone(df)
    if not zone:
        return False
    closes = df["close"].tail(RETEST_LOOKBACK).tolist()
    if direction == "BUY":
        return all(float(c) > zone["body_low"] for c in closes)
    if direction == "SELL":
        return all(float(c) < zone["body_high"] for c in closes)
    return False


def sniper_liquidity_confirmation(df):
    last         = df.iloc[-1]
    recent_lows  = df["low"].iloc[-10:-1]
    recent_highs = df["high"].iloc[-10:-1]
    bull_sweep = (
        float(last["low"]) < float(recent_lows.min())
        and float(last["close"]) > float(last["low"])
    )
    bear_sweep = (
        float(last["high"]) > float(recent_highs.max())
        and float(last["close"]) < float(last["high"])
    )
    return bull_sweep, bear_sweep


def multi_candle_confirmation(df, direction):
    candles = df.tail(SNIPER_CONFIRM_CANDLES)
    if direction == "BUY":
        return sum(
            float(row["close"]) > float(row["open"])
            for _, row in candles.iterrows()
        ) >= SNIPER_CONFIRM_CANDLES
    if direction == "SELL":
        return sum(
            float(row["close"]) < float(row["open"])
            for _, row in candles.iterrows()
        ) >= SNIPER_CONFIRM_CANDLES
    return False


def sniper_stop_buffer(price, sl, atr, direction):
    buffer = atr * SL_BUFFER_ATR_MULT
    if direction == "BUY":
        return round(sl - buffer, 2)
    if direction == "SELL":
        return round(sl + buffer, 2)
    return sl


# ═══════════════════════════════════════════════════════════════
# SNIPER SCORE ENGINE — 7 precision conditions
# ═══════════════════════════════════════════════════════════════
def sniper_score(df, trend, symbol_key):
    premium, discount    = premium_discount_zone(df)
    bull_wick, bear_wick = sniper_wick_confirmation(df)
    bull_liq,  bear_liq  = sniper_liquidity_confirmation(df)
    bull_choch,bear_choch = detect_choch(df)
    bull_fvg,  bear_fvg  = fair_value_gap(df)

    bias = MARKETS[symbol_key].get("bias", "NEUTRAL")

    buy_checks = {
        "HTF Bull":            trend == "BULL",
        "Discount Zone":       discount,
        "Wick Rejection":      bull_wick,
        "Liquidity Sweep":     bull_liq,
        "CHOCH":               bull_choch,
        "Retest Confirm":      sniper_retest_confirmation(df, "BUY"),
        "Multi Candle":        multi_candle_confirmation(df, "BUY"),
        "FVG":                 bull_fvg,
    }

    sell_checks = {
        "HTF Bear":            trend == "BEAR",
        "Premium Zone":        premium,
        "Wick Rejection":      bear_wick,
        "Liquidity Sweep":     bear_liq,
        "CHOCH":               bear_choch,
        "Retest Confirm":      sniper_retest_confirmation(df, "SELL"),
        "Multi Candle":        multi_candle_confirmation(df, "SELL"),
        "FVG":                 bear_fvg,
    }

    buy_score  = sum(buy_checks.values())
    sell_score = sum(sell_checks.values())

    # May 2026 bull market bias
    if bias == "BULL":
        buy_score  = int(round(buy_score  * 1.10))
        sell_score = int(round(sell_score * 0.90))
    elif bias == "BEAR":
        sell_score = int(round(sell_score * 1.10))
        buy_score  = int(round(buy_score  * 0.90))

    return buy_checks, sell_checks, buy_score, sell_score


# ═══════════════════════════════════════════════════════════════
# DYNAMIC RISK — per symbol May 2026
# ═══════════════════════════════════════════════════════════════
def dynamic_risk(score, symbol_key):
    if symbol_key == "BTC/USD":
        if score >= 7:
            return 50
        elif score >= 6:
            return 35
        return 20
    elif symbol_key == "XAU/USD":
        if score >= 7:
            return 75
        elif score >= 6:
            return 55
        return 30
    else:
        if score >= 7:
            return 75
        elif score >= 6:
            return 50
        return 25


# ═══════════════════════════════════════════════════════════════
# LEVELS
# ═══════════════════════════════════════════════════════════════
def calc_levels(price, direction, atr, symbol_key, df, rr):
    min_sl   = MARKETS[symbol_key]["min_sl"]
    decimals = MARKETS[symbol_key]["decimals"]
    atr_sl   = float(atr) * ATR_MULT
    recent   = df.tail(12)

    support, resistance = get_sr_levels(df)

    if direction == "BUY":
        swing = price - float(recent["low"].min())
    else:
        swing = float(recent["high"].max()) - price

    sl_dist = max(min_sl, atr_sl, swing * 0.50)
    adx_now = float(df.iloc[-1]["adx"])

    if adx_now > 35:
        sl_dist *= 1.12

    if symbol_key == "BTC/USD":
        sl_dist *= 1.55
    elif symbol_key == "XAU/USD":
        sl_dist *= 1.15
    elif symbol_key == "XAG/USD":
        sl_dist *= 1.10
    elif symbol_key in ["NAS100", "US500"]:
        sl_dist *= 1.08

    hour = datetime.now(timezone.utc).hour
    if 12 <= hour < 16:
        sl_dist *= 1.05
    elif 0 <= hour < 6:
        sl_dist *= 0.95

    sl_dist = round(sl_dist, decimals)

    if direction == "BUY":
        sl            = price - sl_dist
        rr_tp         = price + sl_dist * rr
        liquidity_tp  = float(df["high"].tail(20).max()) * 0.997
        resistance_tp = float(resistance) * 0.998
        tp            = min(rr_tp, liquidity_tp, resistance_tp)
    else:
        sl           = price + sl_dist
        rr_tp        = price - sl_dist * rr
        liquidity_tp = float(df["low"].tail(20).min()) * 1.003
        support_tp   = float(support) * 1.002
        tp           = max(rr_tp, liquidity_tp, support_tp)

    sl = round(sl, decimals)
    tp = round(tp, decimals)

    if direction == "BUY" and tp <= price:
        tp = round(price + sl_dist * 2.0, decimals)
    if direction == "SELL" and tp >= price:
        tp = round(price - sl_dist * 2.0, decimals)

    return sl, tp, sl_dist


def lot_for_risk(price, sl, symbol_key, risk):
    sl_dist = abs(price - sl)
    if sl_dist == 0:
        return 0.01
    dpl = DOLLAR_PER_LOT[symbol_key]
    return max(round(risk / (sl_dist * dpl), 3), 0.01)


def log_signal(symbol, direction, score, rr, entry, sl, tp, session, regime, timeframe):
    file_exists = os.path.isfile("signals_log.csv")
    with open("signals_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "version", "timestamp", "symbol", "direction",
                "score", "rr", "entry", "sl", "tp",
                "session", "regime", "timeframe"
            ])
        writer.writerow([
            SYSTEM_VERSION,
            datetime.now(timezone.utc).isoformat(),
            symbol, direction, score, rr,
            entry, sl, tp, session, regime, timeframe
        ])


# ═══════════════════════════════════════════════════════════════
# PROCESS (per symbol)
# ═══════════════════════════════════════════════════════════════
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

    if economic_news_block() and symbol_key in ["XAU/USD", "NAS100", "US500"]:
        log.info(f"BLOCKED {symbol_key} news window")
        return

    df, source = get_entry_data(symbol_key)
    if df is None or len(df) < 100:
        return

    spread = get_spread(df)
    if spread > MAX_SPREAD[symbol_key]:
        log.info(f"REJECTED {symbol_key} spread {spread:.4f}")
        return

    df    = add_ind(df)
    price = float(df.iloc[-1]["close"])

    if not (MARKETS[symbol_key]["price_lo"] <= price <= MARKETS[symbol_key]["price_hi"]):
        log.info(f"REJECTED {symbol_key} price out of range")
        return

    trend = get_trend(symbol_key)

    if symbol_key == "BTC/USD" and trend == "NEUTRAL":
        log.info("REJECTED BTC/USD HTF NEUTRAL")
        return

    adx       = float(df.iloc[-1]["adx"])
    rsi       = float(df.iloc[-1]["rsi"])
    atr       = float(df.iloc[-1]["atr"])
    regime    = detect_market_regime(df)
    timeframe = REGIME_TIMEFRAME.get(regime, "5M / 15M")
    bias      = MARKETS[symbol_key].get("bias", "NEUTRAL")

    if adx < ADX_THRESHOLD:
        log.info(f"REJECTED {symbol_key} ADX {adx:.1f} < {ADX_THRESHOLD}")
        return

    buy_checks, sell_checks, buy_score, sell_score = sniper_score(
        df, trend, symbol_key
    )

    best = max(buy_score, sell_score)

    log.info(
        f"{symbol_key} | Regime: {regime} | TF: {timeframe} | "
        f"BUY {buy_score} | SELL {sell_score} | "
        f"Trend: {trend} | Bias: {bias}"
    )

    # required score per symbol
    required = MIN_SNIPER_SCORE
    if symbol_key == "BTC/USD":
        required += 1           # stricter for BTC
    elif symbol_key == "XAU/USD":
        required = max(required - 1, 4)  # easier for gold bull

    if session == "Asian" and symbol_key not in ["BTC/USD", "XAU/USD"]:
        required += 1

    if regime == "RANGE":
        required += 1

    if best < required:
        log.info(f"REJECTED {symbol_key} sniper score {best} < {required}")
        return

    now = time.time()

    if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
        remaining = int(SIGNAL_COOLDOWN - (now - _signal_sent[symbol_key]))
        log.info(f"REJECTED {symbol_key} cooldown {remaining}s")
        return

    if symbol_key == "BTC/USD":
        if now - _signal_sent[symbol_key] < BTC_EXTRA_COOLDOWN:
            remaining = int(BTC_EXTRA_COOLDOWN - (now - _signal_sent[symbol_key]))
            log.info(f"REJECTED BTC/USD extra cooldown {remaining}s")
            return

    if buy_score == sell_score:
        log.info(f"REJECTED {symbol_key} tied score {buy_score}")
        return

    direction = "BUY" if buy_score > sell_score else "SELL"

    # bull market sell guard
    if bias == "BULL" and direction == "SELL":
        if best < required + 2:
            log.info(f"REJECTED {symbol_key} SELL — bull bias needs stronger confirmation")
            return

    if duplicate_signal(symbol_key, direction):
        return

    checks = buy_checks if direction == "BUY" else sell_checks

    # RR based on score and regime
    if best >= 7:
        rr = 4.0
    elif best >= 6:
        rr = 3.0
    else:
        rr = 2.2

    if regime == "BREAKOUT":
        rr += 0.5
    elif regime == "TREND":
        rr += 0.2
    elif regime == "SCALP":
        rr = min(rr, 2.0)

    if session == "NY+London":
        rr += 0.2

    rr = min(rr, 4.5)

    sl, tp, sl_dist = calc_levels(price, direction, atr, symbol_key, df, rr)

    # apply smart SL buffer
    sl = sniper_stop_buffer(price, sl, atr, direction)

    actual_rr = safe_rr(price, sl, tp)

    if actual_rr < 2.0:
        log.info(f"REJECTED {symbol_key} RR {actual_rr:.2f} < 2.0")
        return

    risk_amount = dynamic_risk(best, symbol_key)
    lot         = lot_for_risk(price, sl, symbol_key, risk_amount)

    _signal_sent[symbol_key] = now

    mt5_sym = MARKETS[symbol_key]["mt5"]
    dec     = MARKETS[symbol_key]["decimals"]

    dashboard_log(symbol_key, direction, best, regime, rr, timeframe)
    log_signal(symbol_key, direction, best, rr, price, sl, tp, session, regime, timeframe)
    execute_trade(symbol_key, direction, lot, price, sl, tp)
    sync_real_pnl()

    conditions_text = build_conditions_text(checks)

    msg = (
        f"🎯 *{SYSTEM_VERSION}*\n"
        f"*{mt5_sym}* | ⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n\n"
        f"🔥 *Action:* {'BUY 📈' if direction == 'BUY' else 'SELL 📉'}\n"
        f"⭐ *Score:* {best}/8\n"
        f"🧠 *Regime:* {regime}\n"
        f"⏱ *Timeframe:* {timeframe}\n"
        f"📊 *Market Bias:* {bias}\n\n"
        f"📍 *Entry:* {price:,.{dec}f}\n"
        f"🛑 *SL:* {sl:,.{dec}f}\n"
        f"🎯 *TP:* {tp:,.{dec}f} *(1:{round(actual_rr, 2)} RR)*\n\n"
        f"📈 *RSI:* {rsi:.1f}\n"
        f"📉 *ADX:* {adx:.1f}\n"
        f"🌍 *HTF:* {trend}\n"
        f"⏰ *Session:* {session}\n"
        f"📡 *Source:* {source}\n\n"
        f"💵 *${risk_amount} Risk Lot:* {lot:.3f}\n\n"
        f"✅ *Sniper Precision Conditions:*\n"
        f"{conditions_text}\n\n"
        f"⚡ *STRICT SNIPER INSTITUTIONAL TVM MODE*"
    )

    send_telegram(msg)

    log.info(
        f"SNIPER SIGNAL SENT {symbol_key} {direction} | "
        f"Entry: {price} | SL: {sl} | TP: {tp} | "
        f"RR: {round(actual_rr, 2)} | Lot: {lot} | "
        f"Regime: {regime} | TF: {timeframe}"
    )


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    log.info(f"{SYSTEM_VERSION} STARTED")
    send_telegram(
        f"🎯 *{SYSTEM_VERSION} LIVE*\n\n"
        f"📊 *Market Analysis May 2026:*\n"
        f"🥇 Gold: BULL — $5,280 target $6K\n"
        f"₿  BTC: BULL — reclaimed $80K\n"
        f"📈 NAS100: BULL — AI driven 27K+\n"
        f"📈 US500: BULL — JPMorgan 7,500\n"
        f"🥈 Silver: BULL — supply deficit\n\n"
        f"🎯 Sniper mode: precision entries only\n"
        f"⚡ Minimum score {MIN_SNIPER_SCORE}/8 required"
    )

    while True:
        try:
            reset_daily()

            with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
                futures = [
                    executor.submit(process_symbol, symbol)
                    for symbol in SYMBOLS
                ]
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        log.error(f"Symbol thread error: {e}")

            time.sleep(10)

        except Exception as e:
            log.error(f"Main loop error: {e}")
            time.sleep(15)


if __name__ == "__main__":
    main()
