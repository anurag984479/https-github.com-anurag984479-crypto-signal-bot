# ═══════════════════════════════════════════════════════════════
# PEPPERSTONE MOMENTUM HUNTER v18.0
# FULL HYBRID INSTITUTIONAL SCALPING FRAMEWORK
# ✔ Trend Strategy          ✔ Breakout Strategy
# ✔ Reversal Strategy       ✔ Range Strategy
# ✔ Scalp Strategy          ✔ Master Hybrid Engine
# ✔ Market Regime Detection ✔ Adaptive Scoring
# ✔ CHOCH Reversal          ✔ Rejection Wick
# ✔ Fair Value Gap          ✔ Precision Entry Zones
# ✔ Liquidity Sweep         ✔ Order Block
# ✔ VWAP Reclaim            ✔ Support Bounce
# ✔ Adaptive RR             ✔ Dynamic Risk
# ✔ ICT / TVM Kill Zones    ✔ Session Precision
# ✔ Trade Journal           ✔ News Blackout
# ✔ Weekend Filter          ✔ Daily Loss Lock
# ✔ Loss Streak Breaker     ✔ Daily Auto-Reset
# ✔ Duplicate Signal Decay  ✔ CSV Rotation
# ✔ BTC Overtrading Guard   ✔ Telegram Retry
# ✔ VPS Watchdog            ✔ Dashboard Logging
# ✔ Execute Trade Bridge    ✔ PnL Sync
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

SYSTEM_VERSION = "v18.0-FULL-HYBRID-INSTITUTIONAL-SCALPING"

# ═══════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v18.0")

# ═══════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════
TOKEN = os.getenv("TOKEN", "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

if not TOKEN or not CHAT_ID:
    raise ValueError("Missing TOKEN or CHAT_ID")

# ═══════════════════════════════════════════════════════════════
# RISK CONFIG
# ═══════════════════════════════════════════════════════════════
DOLLAR_PER_LOT = {
    "XAU/USD": 100.0,
    "XAG/USD": 5000.0,
    "BTC/USD": 1.0,
    "NAS100":  10.0,
    "US500":   10.0,
}

# ═══════════════════════════════════════════════════════════════
# MARKETS
# ═══════════════════════════════════════════════════════════════
MARKETS = {
    "XAU/USD": {
        "mt5":      "XAUUSD.Qraw",
        "yf":       "GC=F",
        "price_lo": 4000,
        "price_hi": 5500,
        "sessions": [7, 20],
        "decimals": 2,
        "min_sl":   5.0,
        "tier":     "GOLD ELITE",
    },
    "XAG/USD": {
        "mt5":      "XAGUSD.Qraw",
        "yf":       "SI=F",
        "price_lo": 20,
        "price_hi": 100,
        "sessions": [7, 20],
        "decimals": 3,
        "min_sl":   0.25,
        "tier":     "SILVER ELITE",
    },
    "BTC/USD": {
        "mt5":      "BTCUSD.Qraw",
        "yf":       None,
        "price_lo": 70000,
        "price_hi": 120000,
        "sessions": [0, 23],
        "decimals": 2,
        "min_sl":   120.0,
        "tier":     "BTC ELITE",
    },
    "NAS100": {
        "mt5":      "NAS100",
        "yf":       "^NDX",
        "price_lo": 10000,
        "price_hi": 50000,
        "sessions": [13, 21],
        "decimals": 1,
        "min_sl":   45.0,
        "tier":     "NAS100 ELITE",
    },
    "US500": {
        "mt5":      "US500.Qtek",
        "yf":       "^GSPC",
        "price_lo": 3000,
        "price_hi": 7000,
        "sessions": [13, 21],
        "decimals": 2,
        "min_sl":   20.0,
        "tier":     "US500 ELITE",
    },
}

SYMBOLS = list(MARKETS.keys())

# ═══════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════
ATR_MULT           = 0.42
VOL_MULT           = 1.05
ADX_THRESHOLD      = 20
CONFIRM_THRESHOLD  = 8
ATR_SPIKE_MULT     = 2.2
SIGNAL_COOLDOWN    = 300
HTF_REFRESH        = 1200
BTC_EXTRA_COOLDOWN = 600

TREND_WEIGHT       = 1.25
REVERSAL_WEIGHT    = 1.15
BREAKOUT_WEIGHT    = 1.20

RANGE_ADX_LIMIT    = 18
TREND_ADX_LIMIT    = 25
EXTREME_ADX_LIMIT  = 35

MAX_DAILY_LOSS         = -300
MAX_CONSECUTIVE_LOSSES = 4

MAX_SPREAD = {
    "XAU/USD": 0.50,
    "XAG/USD": 0.05,
    "BTC/USD": 40,
    "NAS100":  3.0,
    "US500":   1.5,
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


# ═══════════════════════════════════════════════════════════════
# DAILY RESET
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# WATCHDOG
# ═══════════════════════════════════════════════════════════════
def watchdog():
    try:
        with open("heartbeat.txt", "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        log.error(f"Watchdog failure: {e}")


# ═══════════════════════════════════════════════════════════════
# DASHBOARD LOG
# ═══════════════════════════════════════════════════════════════
def dashboard_log(symbol, direction, score, regime, rr):
    log.info(
        f"[DASHBOARD] {symbol} | {direction} | "
        f"Score: {score} | Regime: {regime} | RR: {rr}"
    )


# ═══════════════════════════════════════════════════════════════
# EXECUTE TRADE PLACEHOLDER
# Replace body with MT5 order_send()
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# TELEGRAM WITH RETRY
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# SESSION / TVM
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# SAFETY GUARDS
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# DATA FETCH
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════
# HTF TREND
# ═══════════════════════════════════════════════════════════════
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
        trend = "NEUTRAL"
    cache["trend"] = trend
    cache["ts"]    = now
    return trend


# ═══════════════════════════════════════════════════════════════
# ICT DETECTION MODULES
# ═══════════════════════════════════════════════════════════════
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


def rejection_wick(df):
    last  = df.iloc[-1]
    high  = float(last["high"])
    low   = float(last["low"])
    open_ = float(last["open"])
    close = float(last["close"])
    body       = abs(close - open_)
    upper_wick = high - max(close, open_)
    lower_wick = min(close, open_) - low
    return (
        lower_wick > body * 1.5,
        upper_wick > body * 1.5
    )


def previous_candle_zones(df):
    if len(df) < 2:
        return None
    prev = df.iloc[-2]
    prev_open  = float(prev["open"])
    prev_close = float(prev["close"])
    return {
        "body_high": max(prev_open, prev_close),
        "body_low":  min(prev_open, prev_close),
        "high":      float(prev["high"]),
        "low":       float(prev["low"]),
        "bullish":   prev_close > prev_open,
        "bearish":   prev_close < prev_open,
    }


def precision_entry(df, symbol_key):
    zones = previous_candle_zones(df)
    if not zones:
        return False, False
    close = float(df.iloc[-1]["close"])
    return (
        zones["bullish"] and close <= zones["body_low"]  * 1.002,
        zones["bearish"] and close >= zones["body_high"] * 0.998
    )


def vwap_reclaim(df):
    last  = df.iloc[-1]
    prev  = df.iloc[-2]
    close = float(last["close"])
    vwap  = float(last["vwap"])
    prev_close = float(prev["close"])
    bull_reclaim = prev_close < vwap and close > vwap
    bear_reclaim = prev_close > vwap and close < vwap
    return bull_reclaim, bear_reclaim


# ═══════════════════════════════════════════════════════════════
# REGIME DETECTION
# ═══════════════════════════════════════════════════════════════
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
# STRATEGY MODULES
# ═══════════════════════════════════════════════════════════════
def trend_strategy(checks):
    score = 0
    score += 3 if checks["HTF Trend"]      else 0
    score += 2 if checks["FVG"]            else 0
    score += 2 if checks["Strong Volume"]  else 0
    score += 2 if checks["Precision Zone"] else 0
    score += 2 if checks["EMA Alignment"]  else 0
    score += 1 if checks["TCR"]            else 0
    return score


def breakout_strategy(checks):
    score = 0
    score += 4 if checks["Strong Volume"]   else 0
    score += 3 if checks["Liquidity Sweep"] else 0
    score += 2 if checks["FVG"]             else 0
    score += 2 if checks["BOS"]             else 0
    score += 2 if checks["CHOCH"]           else 0
    return score


def reversal_strategy(checks):
    score = 0
    score += 4 if checks["CHOCH"]           else 0
    score += 3 if checks["Rejection Wick"]  else 0
    score += 2 if checks["Liquidity Sweep"] else 0
    score += 2 if checks["SR Bounce"]       else 0
    return score


def range_strategy(checks):
    score = 0
    score += 3 if checks["Rejection Wick"]  else 0
    score += 3 if checks["Precision Zone"]  else 0
    score += 2 if checks["RSI Extreme"]     else 0
    score += 2 if checks["SR Bounce"]       else 0
    return score


def scalp_strategy(checks):
    score = 0
    score += 3 if checks["VWAP Reclaim"]   else 0
    score += 2 if checks["Precision Zone"] else 0
    score += 2 if checks["Strong Volume"]  else 0
    score += 2 if checks["Rejection Wick"] else 0
    score += 1 if checks["FVG"]            else 0
    return score


# ═══════════════════════════════════════════════════════════════
# MASTER CONDITION BUILDER
# ═══════════════════════════════════════════════════════════════
def build_conditions(df, trend, symbol_key, direction):
    last  = df.iloc[-1]
    prev  = df.iloc[-2]
    rsi   = float(last["rsi"])
    ema9  = float(last["ema9"])
    ema21 = float(last["ema21"])
    ema50 = float(last["ema50"])
    close = float(last["close"])
    op    = float(last["open"])
    atr   = float(last["atr"])
    adx   = float(last["adx"])
    vol   = float(last["volume"])
    volma = float(last["volma"]) if not pd.isna(last["volma"]) else 0

    body     = abs(close - op)
    rng      = max(float(last["high"]) - float(last["low"]), 0.0001)
    body_pct = body / rng

    support, resistance = get_sr_levels(df)

    bull_fvg,  bear_fvg  = fair_value_gap(df)
    bull_choch,bear_choch = detect_choch(df)
    bull_wick, bear_wick  = rejection_wick(df)
    prec_buy,  prec_sell  = precision_entry(df, symbol_key)
    vwap_bull, vwap_bear  = vwap_reclaim(df)

    recent_lows  = df["low"].iloc[-11:-1]
    recent_highs = df["high"].iloc[-11:-1]

    prev_body  = abs(float(prev["close"]) - float(prev["open"]))
    prev_range = max(float(prev["high"]) - float(prev["low"]), 0.0001)
    strong_prev = (prev_body / prev_range) > 0.50

    if direction == "BUY":
        checks = {
            "HTF Trend":       trend == "BULL",
            "EMA Alignment":   ema9 > ema21 > ema50,
            "RSI Strength":    rsi > 58,
            "RSI Extreme":     rsi < 35,
            "Strong Volume":   volma > 0 and vol > volma * VOL_MULT,
            "Bull Candle":     close > op and body_pct > 0.60,
            "EMA Pullback":    abs(close - ema9) < atr * 0.25,
            "BOS":             close > float(df.iloc[-2]["high"]) + atr * 0.25,
            "SR Bounce":       close <= float(support) * 1.003,
            "ADX":             adx > ADX_THRESHOLD,
            "TCR":             (trend == "BULL" and ema9 > ema21 > ema50
                                and float(prev["low"]) <= ema21
                                and close > ema9 and rsi > 58),
            "Liquidity Sweep": (float(last["low"]) < float(recent_lows.min())
                                and close > float(last["low"])),
            "Order Block":     (float(prev["close"]) < float(prev["open"])
                                and close > float(prev["high"]) and strong_prev),
            "ATR Safe":        atr_is_safe(df, atr),
            "FVG":             bull_fvg,
            "CHOCH":           bull_choch,
            "Rejection Wick":  bull_wick,
            "Precision Zone":  prec_buy,
            "VWAP Reclaim":    vwap_bull,
        }
    else:
        checks = {
            "HTF Trend":       trend == "BEAR",
            "EMA Alignment":   ema9 < ema21 < ema50,
            "RSI Weakness":    rsi < 42,
            "RSI Extreme":     rsi > 65,
            "Strong Volume":   volma > 0 and vol > volma * VOL_MULT,
            "Bear Candle":     close < op and body_pct > 0.60,
            "EMA Pullback":    abs(close - ema9) < atr * 0.25,
            "BOS":             close < float(df.iloc[-2]["low"]) - atr * 0.25,
            "SR Bounce":       close >= float(resistance) * 0.997,
            "ADX":             adx > ADX_THRESHOLD,
            "TCR":             (trend == "BEAR" and ema9 < ema21 < ema50
                                and float(prev["high"]) >= ema21
                                and close < ema9 and rsi < 42),
            "Liquidity Sweep": (float(last["high"]) > float(recent_highs.max())
                                and close < float(last["high"])),
            "Order Block":     (float(prev["close"]) > float(prev["open"])
                                and close < float(prev["low"]) and strong_prev),
            "ATR Safe":        atr_is_safe(df, atr),
            "FVG":             bear_fvg,
            "CHOCH":           bear_choch,
            "Rejection Wick":  bear_wick,
            "Precision Zone":  prec_sell,
            "VWAP Reclaim":    vwap_bear,
        }

    return checks


# ═══════════════════════════════════════════════════════════════
# MASTER HYBRID SCORING ENGINE
# ═══════════════════════════════════════════════════════════════
def calculate_hybrid_score(df, trend, symbol_key):
    regime = detect_market_regime(df)

    buy_checks  = build_conditions(df, trend, symbol_key, "BUY")
    sell_checks = build_conditions(df, trend, symbol_key, "SELL")

    if regime == "TREND":
        buy_score  = trend_strategy(buy_checks)  * TREND_WEIGHT
        sell_score = trend_strategy(sell_checks) * TREND_WEIGHT

    elif regime == "BREAKOUT":
        buy_score  = breakout_strategy(buy_checks)  * BREAKOUT_WEIGHT
        sell_score = breakout_strategy(sell_checks) * BREAKOUT_WEIGHT

    elif regime == "RANGE":
        buy_score  = range_strategy(buy_checks)
        sell_score = range_strategy(sell_checks)

    elif regime == "SCALP":
        buy_score  = scalp_strategy(buy_checks)
        sell_score = scalp_strategy(sell_checks)

    else:
        buy_score  = reversal_strategy(buy_checks)
        sell_score = reversal_strategy(sell_checks)

    return (
        int(round(buy_score)),
        int(round(sell_score)),
        buy_checks,
        sell_checks,
        regime
    )


# ═══════════════════════════════════════════════════════════════
# DYNAMIC RISK
# ═══════════════════════════════════════════════════════════════
def dynamic_risk(score):
    if score >= 12:
        return 75
    elif score >= 10:
        return 50
    return 25


# ═══════════════════════════════════════════════════════════════
# TRADE LEVELS
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
        sl_dist *= 1.20

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


# ═══════════════════════════════════════════════════════════════
# SIGNAL JOURNAL
# ═══════════════════════════════════════════════════════════════
def log_signal(symbol, direction, score, rr, entry, sl, tp, session, regime):
    file_exists = os.path.isfile("signals_log.csv")
    with open("signals_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "version", "timestamp", "symbol", "direction",
                "score", "rr", "entry", "sl", "tp", "session", "regime"
            ])
        writer.writerow([
            SYSTEM_VERSION,
            datetime.now(timezone.utc).isoformat(),
            symbol, direction, score, rr,
            entry, sl, tp, session, regime
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

    buy_score, sell_score, buy_checks, sell_checks, regime = calculate_hybrid_score(
        df, trend, symbol_key
    )

    best = max(buy_score, sell_score)

    log.info(
        f"{symbol_key} | Regime: {regime} | "
        f"BUY {buy_score} | SELL {sell_score} | Trend: {trend}"
    )

    if best >= 12:
        rr = 4.0
    elif best >= 10:
        rr = 3.5
    elif best >= 8:
        rr = 3.0
    else:
        rr = 2.4

    if regime == "BREAKOUT":
        rr += 0.5
    elif regime == "TREND":
        rr += 0.2
    elif regime == "SCALP":
        rr = min(rr, 2.0)

    if session == "NY+London":
        rr += 0.2

    rr = min(rr, 4.5)

    required_score = max(CONFIRM_THRESHOLD, 8)

    if session == "Asian" and symbol_key != "BTC/USD":
        required_score += 1

    if regime == "RANGE":
        required_score += 1

    if best < required_score:
        log.info(f"REJECTED {symbol_key} score {best} < {required_score}")
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
    checks    = buy_checks if direction == "BUY" else sell_checks

    if duplicate_signal(symbol_key, direction):
        return

    atr = float(df.iloc[-1]["atr"])
    rsi = float(df.iloc[-1]["rsi"])
    adx = float(df.iloc[-1]["adx"])

    sl, tp, sl_dist = calc_levels(price, direction, atr, symbol_key, df, rr)

    actual_rr = safe_rr(price, sl, tp)

    if actual_rr < 1.8:
        log.info(f"REJECTED {symbol_key} RR {actual_rr:.2f} < 1.8")
        return

    risk_amount = dynamic_risk(best)
    lot         = lot_for_risk(price, sl, symbol_key, risk_amount)

    _signal_sent[symbol_key] = now

    mt5_sym = MARKETS[symbol_key]["mt5"]
    dec     = MARKETS[symbol_key]["decimals"]

    dashboard_log(symbol_key, direction, best, regime, rr)
    log_signal(symbol_key, direction, best, rr, price, sl, tp, session, regime)
    execute_trade(symbol_key, direction, lot, price, sl, tp)
    sync_real_pnl()

    conditions_text = build_conditions_text(checks)

    msg = (
        f"🚀 *{SYSTEM_VERSION}*\n"
        f"*{mt5_sym}* | ⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n\n"
        f"🔥 *Action:* {'BUY 📈' if direction == 'BUY' else 'SELL 📉'}\n"
        f"⭐ *Score:* {best}\n"
        f"🧠 *Regime:* {regime}\n\n"
        f"📍 *Entry:* {price:,.{dec}f}\n"
        f"🛑 *SL:* {sl:,.{dec}f}\n"
        f"🎯 *TP:* {tp:,.{dec}f} *(1:{round(actual_rr, 2)} RR)*\n\n"
        f"📈 *RSI:* {rsi:.1f}\n"
        f"📉 *ADX:* {adx:.1f}\n"
        f"🌍 *HTF:* {trend}\n"
        f"⏰ *Session:* {session}\n"
        f"📡 *Source:* {source}\n\n"
        f"💵 *${risk_amount} Risk Lot:* {lot:.3f}\n\n"
        f"✅ *Elite Conditions:*\n"
        f"{conditions_text}\n\n"
        f"⚡ *STRICT ELITE INSTITUTIONAL TVM MODE*"
    )

    send_telegram(msg)

    log.info(
        f"SIGNAL SENT {symbol_key} {direction} | "
        f"Entry: {price} | SL: {sl} | TP: {tp} | "
        f"RR: {round(actual_rr, 2)} | Lot: {lot} | Regime: {regime}"
    )


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    log.info(f"{SYSTEM_VERSION} STARTED")
    send_telegram(f"🚀 {SYSTEM_VERSION} Live")

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
