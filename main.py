# ============================================================
# PEPPERSTONE MOMENTUM HUNTER v21.0-GLOBAL-ELITE-PRO+
# 11 MARKETS — FULL INSTITUTIONAL PRECISION ENGINE
# ✔ BTC / ETH / SOL          ✔ Gold / Silver
# ✔ NAS100 / US500 / DAX40   ✔ EUR/USD / GBP/USD
# ✔ WTI Oil                  ✔ Partial Institutional Entry
# ✔ Per-Symbol RSI Bands      ✔ Breakout Chase Filter
# ✔ Pullback Confirmation     ✔ Smart SL Engine
# ============================================================

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

SYSTEM_VERSION = "v21.0-GLOBAL-ELITE-PRO+"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v21.0")

TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

# ============================================================
# MARKETS — 11 markets
# ============================================================
MARKETS = {
    "BTC/USD": {
        "mt5":      "BTCUSD.Qraw",
        "yf":       None,
        "price_lo": 50000,
        "price_hi": 150000,
        "sessions": [0, 23],
        "decimals": 2,
        "min_sl":   250.0,
        "tier":     "BTC ELITE",
        "bias":     "BULL",
    },
    "ETH/USD": {
        "mt5":      "ETHUSD.Qraw",
        "yf":       None,
        "price_lo": 1500,
        "price_hi": 10000,
        "sessions": [0, 23],
        "decimals": 2,
        "min_sl":   18.0,
        "tier":     "ETH ELITE",
        "bias":     "BULL",
    },
    "SOL/USD": {
        "mt5":      "SOLUSD.Qraw",
        "yf":       None,
        "price_lo": 20,
        "price_hi": 500,
        "sessions": [0, 23],
        "decimals": 2,
        "min_sl":   2.50,
        "tier":     "SOL ELITE",
        "bias":     "BULL",
    },
    "XAU/USD": {
        "mt5":      "XAUUSD.Qraw",
        "yf":       "GC=F",
        "price_lo": 4000,
        "price_hi": 7000,
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
    "NAS100": {
        "mt5":      "USTEC.Qraw",
        "yf":       "^NDX",
        "price_lo": 15000,
        "price_hi": 30000,
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
    "DAX40": {
        "mt5":      "DE30.Qraw",
        "yf":       "^GDAXI",
        "price_lo": 15000,
        "price_hi": 25000,
        "sessions": [7, 18],
        "decimals": 1,
        "min_sl":   45.0,
        "tier":     "DAX ELITE",
        "bias":     "BULL",
    },
    "EUR/USD": {
        "mt5":      "EURUSD.Qraw",
        "yf":       "EURUSD=X",
        "price_lo": 1.00,
        "price_hi": 1.25,
        "sessions": [6, 20],
        "decimals": 5,
        "min_sl":   0.0012,
        "tier":     "FOREX ELITE",
        "bias":     "NEUTRAL",
    },
    "GBP/USD": {
        "mt5":      "GBPUSD.Qraw",
        "yf":       "GBPUSD=X",
        "price_lo": 1.10,
        "price_hi": 1.40,
        "sessions": [6, 20],
        "decimals": 5,
        "min_sl":   0.0015,
        "tier":     "FOREX ELITE",
        "bias":     "NEUTRAL",
    },
    "WTI/USD": {
        "mt5":      "WTIUSD.Qraw",
        "yf":       "CL=F",
        "price_lo": 40,
        "price_hi": 130,
        "sessions": [13, 22],
        "decimals": 2,
        "min_sl":   1.20,
        "tier":     "OIL ELITE",
        "bias":     "NEUTRAL",
    },
}

SYMBOLS = [
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "XAU/USD",
    "XAG/USD",
    "NAS100",
    "US500",
    "DAX40",
    "EUR/USD",
    "GBP/USD",
    "WTI/USD",
]

# ============================================================
# SETTINGS
# ============================================================
ATR_MULT               = 0.30
VOL_MULT               = 1.15
ADX_THRESHOLD          = 24
SIGNAL_COOLDOWN        = 1800
HTF_REFRESH            = 1200
MAX_DAILY_LOSS         = -300
MAX_CONSECUTIVE_LOSSES = 4
MIN_SCORE              = 7

ATR_MARKET_MULTIPLIER = {
    "BTC/USD": 1.35,
    "ETH/USD": 1.20,
    "SOL/USD": 1.30,
    "XAU/USD": 1.05,
    "XAG/USD": 1.00,
    "NAS100":  1.03,
    "US500":   1.02,
    "DAX40":   1.08,
    "EUR/USD": 0.90,
    "GBP/USD": 0.90,
    "WTI/USD": 1.15,
}

DOLLAR_PER_POINT = {
    "BTC/USD": 1,
    "ETH/USD": 1,
    "SOL/USD": 10,
    "XAU/USD": 100,
    "XAG/USD": 5000,
    "NAS100":  10,
    "US500":   10,
    "DAX40":   10,
    "EUR/USD": 100000,
    "GBP/USD": 100000,
    "WTI/USD": 100,
}

MAX_SPREAD = {
    "BTC/USD": 60,
    "ETH/USD": 8,
    "SOL/USD": 0.60,
    "XAU/USD": 0.80,
    "XAG/USD": 0.08,
    "NAS100":  4.0,
    "US500":   2.0,
    "DAX40":   4.5,
    "EUR/USD": 0.00025,
    "GBP/USD": 0.00030,
    "WTI/USD": 0.20,
}

RSI_LIMITS = {
    "BTC/USD": (52, 68),
    "ETH/USD": (52, 68),
    "SOL/USD": (54, 72),
    "XAU/USD": (58, 72),
    "XAG/USD": (58, 70),
    "NAS100":  (55, 70),
    "US500":   (55, 70),
    "DAX40":   (55, 70),
    "EUR/USD": (52, 68),
    "GBP/USD": (52, 68),
    "WTI/USD": (54, 70),
}

LOT_CAPS = {
    "BTC/USD": 0.40,
    "ETH/USD": 0.80,
    "SOL/USD": 1.20,
    "XAU/USD": 1.20,
    "XAG/USD": 0.12,
    "NAS100":  1.50,
    "US500":   2.50,
    "DAX40":   1.20,
    "EUR/USD": 2.50,
    "GBP/USD": 2.50,
    "WTI/USD": 1.00,
}

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


def watchdog():
    try:
        with open("heartbeat.txt", "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        log.error(f"Watchdog failure: {e}")


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


# ============================================================
# SAFETY GUARDS
# ============================================================
def weekend_block(symbol_key):
    weekday = datetime.now(timezone.utc).weekday()
    crypto  = ["BTC/USD", "ETH/USD", "SOL/USD"]
    if weekday >= 5 and symbol_key not in crypto:
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
    h = datetime.now(timezone.utc).hour
    return h in [12, 13, 14]


def rotate_log():
    file_path = "signals_log.csv"
    if os.path.isfile(file_path):
        if os.path.getsize(file_path) > 5_000_000:
            os.rename(file_path, f"signals_log_{int(time.time())}.csv")


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


# ============================================================
# DATA FETCH
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
    # ── Crypto via CCXT
    if symbol_key == "BTC/USD":
        for src in ["coinbase", "binance"]:
            pair = "BTC/USDT" if src == "binance" else "BTC/USD"
            df   = fetch_ccxt(src, pair)
            if df is not None and len(df) > 100:
                return df, src

    if symbol_key == "ETH/USD":
        for src in ["coinbase", "binance"]:
            pair = "ETH/USDT" if src == "binance" else "ETH/USD"
            df   = fetch_ccxt(src, pair)
            if df is not None and len(df) > 100:
                return df, src

    if symbol_key == "SOL/USD":
        df = fetch_ccxt("binance", "SOL/USDT")
        if df is not None and len(df) > 100:
            return df, "binance"

    # ── Everything else via yfinance
    yf_sym = MARKETS[symbol_key]["yf"]
    if yf_sym:
        df = fetch_yf(yf_sym)
        if df is not None and len(df) > 100:
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


# ============================================================
# TREND
# ============================================================
def get_trend(symbol_key):
    cache = _htf_cache[symbol_key]
    now   = time.time()
    if now - cache["ts"] < HTF_REFRESH:
        return cache["trend"]
    df, _ = get_entry_data(symbol_key)
    if df is None:
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


# ============================================================
# ICT MODULES
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
# REGIME
# ============================================================
def detect_market_regime(df):
    adx = float(df.iloc[-1]["adx"])
    if adx >= 35:
        return "BREAKOUT"
    elif adx >= 25:
        return "TREND"
    elif adx <= 18:
        return "RANGE"
    return "SCALP"


# ============================================================
# BREAKOUT CHASE FILTER
# ============================================================
def breakout_chase_filter(df, symbol_key):
    last        = df.iloc[-1]
    atr         = float(last["atr"])
    recent_high = float(df.tail(10)["high"].max())
    recent_low  = float(df.tail(10)["low"].min())
    close       = float(last["close"])
    if close > recent_high - atr * 0.15:
        return False
    if close < recent_low + atr * 0.15:
        return False
    return True


# ============================================================
# PULLBACK CONFIRMATION
# ============================================================
def pullback_confirmation(df, direction):
    last  = df.iloc[-1]
    close = float(last["close"])
    ema9  = float(last["ema9"])
    ema21 = float(last["ema21"])
    atr   = float(last["atr"])
    if direction == "BUY":
        return (
            close > ema9
            and abs(close - ema9) < atr * 0.35
            and close > ema21
        )
    else:
        return (
            close < ema9
            and abs(close - ema9) < atr * 0.35
            and close < ema21
        )


# ============================================================
# SCORING ENGINE
# ============================================================
def build_score(df, trend, symbol_key):
    last  = df.iloc[-1]
    rsi   = float(last["rsi"])
    ema9  = float(last["ema9"])
    ema21 = float(last["ema21"])
    ema50 = float(last["ema50"])
    adx   = float(last["adx"])
    vol   = float(last["volume"])
    volma = float(last["volma"]) if not pd.isna(last["volma"]) else 0
    atr   = float(last["atr"])

    bull_fvg,   bear_fvg   = fair_value_gap(df)
    bull_choch, bear_choch = detect_choch(df)

    bullish_break = float(last["close"]) > float(df.iloc[-2]["high"]) + atr * 0.12
    bearish_break = float(last["close"]) < float(df.iloc[-2]["low"])  - atr * 0.12

    rsi_min, rsi_max = RSI_LIMITS[symbol_key]

    buy = {
        "HTF":   trend == "BULL",
        "EMA":   ema9 > ema21 > ema50,
        "RSI":   rsi_min <= rsi <= rsi_max,
        "ADX":   adx > ADX_THRESHOLD,
        "VOL":   volma > 0 and vol > volma * VOL_MULT,
        "FVG":   bull_fvg,
        "CHOCH": bull_choch,
        "BOS":   bullish_break,
    }

    sell = {
        "HTF":   trend == "BEAR",
        "EMA":   ema9 < ema21 < ema50,
        "RSI":   (100 - rsi_max) <= rsi <= (100 - rsi_min),
        "ADX":   adx > ADX_THRESHOLD,
        "VOL":   volma > 0 and vol > volma * VOL_MULT,
        "FVG":   bear_fvg,
        "CHOCH": bear_choch,
        "BOS":   bearish_break,
    }

    buy_score  = sum(buy.values())
    sell_score = sum(sell.values())

    if MARKETS[symbol_key].get("bias") == "BULL":
        buy_score += 1

    return buy, sell, buy_score, sell_score


# ============================================================
# LEVELS
# ============================================================
def calc_levels(price, direction, atr, symbol_key, df):
    min_sl   = MARKETS[symbol_key]["min_sl"]
    decimals = MARKETS[symbol_key]["decimals"]
    recent   = df.tail(8)

    if direction == "BUY":
        swing_sl = price - float(recent["low"].min())
    else:
        swing_sl = float(recent["high"].max()) - price

    atr_sl  = atr * ATR_MULT * ATR_MARKET_MULTIPLIER[symbol_key]
    sl_dist = max(
        min_sl,
        min(
            max(atr_sl, swing_sl * 0.85),
            swing_sl * 1.15
        )
    )

    if symbol_key == "BTC/USD":
        rr = 2.8
    elif symbol_key in ["XAU/USD", "NAS100", "ETH/USD"]:
        rr = 2.7
    elif symbol_key == "SOL/USD":
        rr = 3.0
    elif symbol_key in ["EUR/USD", "GBP/USD"]:
        rr = 2.5
    else:
        rr = 2.5

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
# LOT SIZE — partial institutional entry with per-symbol caps
# ============================================================
def lot_for_risk(price, sl, symbol_key, risk=25):
    sl_dist = abs(price - sl)
    if sl_dist <= 0:
        return 0.01

    full_lot = risk / (sl_dist * DOLLAR_PER_POINT[symbol_key])

    # 65% partial institutional entry
    lot = full_lot * 0.65

    return round(max(0.01, min(lot, LOT_CAPS[symbol_key])), 3)


# ============================================================
# SIGNAL JOURNAL
# ============================================================
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

    if economic_news_block() and symbol_key in [
        "XAU/USD", "NAS100", "US500", "DAX40", "EUR/USD", "GBP/USD", "WTI/USD"
    ]:
        log.info(f"BLOCKED {symbol_key} news window")
        return

    df, source = get_entry_data(symbol_key)
    if df is None or len(df) < 100:
        return

    spread = get_spread(df)
    if spread > MAX_SPREAD[symbol_key]:
        log.info(f"REJECTED {symbol_key} spread {spread:.5f}")
        return

    df    = add_ind(df)
    price = float(df.iloc[-1]["close"])

    if not (MARKETS[symbol_key]["price_lo"] <= price <= MARKETS[symbol_key]["price_hi"]):
        log.info(f"REJECTED {symbol_key} price out of range")
        return

    trend = get_trend(symbol_key)

    crypto = ["BTC/USD", "ETH/USD", "SOL/USD"]
    if symbol_key in crypto and trend == "NEUTRAL":
        log.info(f"REJECTED {symbol_key} HTF NEUTRAL")
        return

    buy, sell, buy_score, sell_score = build_score(df, trend, symbol_key)

    best   = max(buy_score, sell_score)
    regime = detect_market_regime(df)

    timeframe = REGIME_TIMEFRAME.get(regime, "5M / 15M")

    atr = float(df.iloc[-1]["atr"])
    rsi = float(df.iloc[-1]["rsi"])
    adx = float(df.iloc[-1]["adx"])

    # RSI protection filters
    if symbol_key == "XAU/USD" and rsi > 74:
        log.info(f"REJECTED {symbol_key} RSI too high {rsi:.1f}")
        return
    if symbol_key == "XAG/USD" and rsi > 76:
        log.info(f"REJECTED {symbol_key} RSI too high {rsi:.1f}")
        return
    if regime == "RANGE" and best < 7:
        log.info(f"REJECTED {symbol_key} RANGE needs score 7+, got {best}")
        return

    log.info(
        f"{symbol_key} | BUY: {buy_score} | SELL: {sell_score} | "
        f"Regime: {regime} | TF: {timeframe} | "
        f"RSI: {rsi:.1f} | ADX: {adx:.1f} | "
        f"Trend: {trend} | Session: {session}"
    )

    if best < MIN_SCORE:
        log.info(f"REJECTED {symbol_key} score {best} < {MIN_SCORE}")
        return

    if buy_score == sell_score:
        log.info(f"REJECTED {symbol_key} tied score")
        return

    direction = "BUY" if buy_score > sell_score else "SELL"

    bias = MARKETS[symbol_key].get("bias", "NEUTRAL")
    if bias == "BULL" and direction == "SELL":
        if best < MIN_SCORE + 2:
            log.info(f"REJECTED {symbol_key} SELL — bull bias")
            return

    if not breakout_chase_filter(df, symbol_key):
        log.info(f"REJECTED {symbol_key} breakout chase risk")
        return

    if not pullback_confirmation(df, direction):
        log.info(f"REJECTED {symbol_key} weak pullback structure")
        return

    if duplicate_signal(symbol_key, direction):
        return

    now = time.time()
    if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
        remaining = int(SIGNAL_COOLDOWN - (now - _signal_sent[symbol_key]))
        log.info(f"REJECTED {symbol_key} cooldown {remaining}s")
        return

    _signal_sent[symbol_key] = now

    dec = MARKETS[symbol_key]["decimals"]

    sl, tp, sl_dist, rr = calc_levels(price, direction, atr, symbol_key, df)

    actual_rr = round(abs(tp - price) / abs(price - sl), 2) if abs(price - sl) > 0 else 0

    if actual_rr < 2.0:
        log.info(f"REJECTED {symbol_key} RR {actual_rr} < 2.0")
        return

    lot = lot_for_risk(price, sl, symbol_key, 25)

    log_signal(symbol_key, direction, best, rr, price, sl, tp, session, regime, timeframe)
    sync_real_pnl()

    checks    = buy if direction == "BUY" else sell
    cond_text = "\n".join([f" {k}" for k, v in checks.items() if v])

    msg = (
        f"🎯 *{SYSTEM_VERSION}*\n"
        f"*{MARKETS[symbol_key]['mt5']}* | ⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n\n"
        f"🔥 *Action:* {'BUY 📈' if direction == 'BUY' else 'SELL 📉'}\n"
        f"⭐ *Score:* {best}/8\n"
        f"🧠 *Regime:* {regime}\n"
        f"⏱ *Timeframe:* {timeframe}\n"
        f"📊 *Market Bias:* {bias}\n"
        f"🛡 *Entry Mode:* Partial Institutional Precision\n\n"
        f"📍 *Entry:* {price:,.{dec}f}\n"
        f"🛑 *SL:* {sl:,.{dec}f}\n"
        f"🎯 *TP:* {tp:,.{dec}f} *(1:{actual_rr} RR)*\n\n"
        f"📈 *RSI:* {rsi:.1f}\n"
        f"📉 *ADX:* {adx:.1f}\n"
        f"🌍 *Trend:* {trend}\n"
        f"⏰ *Session:* {session}\n"
        f"📡 *Source:* {source}\n\n"
        f"💵 *Lot:* {lot}\n\n"
        f"✅ *Conditions:*\n"
        f"{cond_text}\n\n"
        f"⚡ *HYBRID INSTITUTIONAL PRO MODE*"
    )

    send_telegram(msg)

    log.info(
        f"SIGNAL SENT {symbol_key} {direction} | "
        f"Entry: {price} | SL: {sl} | TP: {tp} | "
        f"RR: {actual_rr} | Regime: {regime} | TF: {timeframe}"
    )


# ============================================================
# MAIN
# ============================================================
def main():
    log.info(f"{SYSTEM_VERSION} STARTED")
    send_telegram(
        f"🚀 *{SYSTEM_VERSION} LIVE*\n\n"
        f"📊 *11 Markets Active:*\n"
        f"₿  BTC/USD\n"
        f"🔷 ETH/USD\n"
        f"🌟 SOL/USD\n"
        f"🥇 XAU/USD\n"
        f"🥈 XAG/USD\n"
        f"📈 NAS100\n"
        f"🇺🇸 US500\n"
        f"🇩🇪 DAX40\n"
        f"💶 EUR/USD\n"
        f"💷 GBP/USD\n"
        f"🛢 WTI/USD\n\n"
        f"🛡 Partial Institutional Entry Active\n"
        f"⚡ Global Elite Pro+ Mode"
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
                        log.error(f"Thread error: {e}")

            time.sleep(15)

        except Exception as e:
            log.error(f"Main loop error: {e}")
            time.sleep(15)


if __name__ == "__main__":
    main()
