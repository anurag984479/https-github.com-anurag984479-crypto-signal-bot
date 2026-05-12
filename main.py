# ============================================================
# PEPPERSTONE MOMENTUM HUNTER v21.5-GLOBAL-ELITE-INSTITUTIONAL
# GOLD + NAS100 + US500 ONLY
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

SYSTEM_VERSION = "v21.5-GLOBAL-ELITE-INSTITUTIONAL"

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
    "NAS100": {
        "mt5":      "NAS100",
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
        "mt5":      "US500.Qraw",
        "yf":       "^GSPC",
        "price_lo": 4500,
        "price_hi": 9000,
        "sessions": [13, 21],
        "decimals": 2,
        "min_sl":   25.0,
        "tier":     "US500 ELITE",
        "bias":     "BULL",
    },
}

SYMBOLS = ["XAU/USD", "NAS100", "US500"]

# ============================================================
# CORE SETTINGS
# ============================================================
ATR_MULT               = 0.28
VOL_MULT               = 1.10           # changed from 1.18
ADX_THRESHOLD          = 25
SIGNAL_COOLDOWN        = 2700           # changed from 3600
HTF_REFRESH            = 900            # changed from 1200
MAX_DAILY_LOSS         = -300
MAX_CONSECUTIVE_LOSSES = 3

# ============================================================
# SCORE THRESHOLDS BY REGIME
# ============================================================
RANGE_MIN_SCORE    = 7
TREND_MIN_SCORE    = 6
REVERSAL_MIN_SCORE = 8                  # changed from 9

# ============================================================
# REVERSAL SETTINGS
# ============================================================
REVERSAL_RSI_OVERBOUGHT = {
    "XAU/USD": 74,
    "NAS100":  78,
    "US500":   77,
}

REVERSAL_RSI_OVERSOLD = {
    "XAU/USD": 29,
    "NAS100":  25,
    "US500":   26,
}

REVERSAL_ADX_MIN     = 30              # changed from 35
REVERSAL_SCORE_BONUS = 2

# ============================================================
# SESSION CURATION
# ============================================================
LONDON_NY_ONLY = ["London", "NY+London"]

# ============================================================
# ATR MULTIPLIERS
# ============================================================
ATR_MARKET_MULTIPLIER = {
    "XAU/USD": 1.05,
    "NAS100":  1.03,
    "US500":   1.02,
}

# ============================================================
# DOLLAR PER POINT
# ============================================================
DOLLAR_PER_POINT = {
    "XAU/USD": 100,
    "NAS100":  10,
    "US500":   10,
}

# ============================================================
# MAX SPREAD
# ============================================================
MAX_SPREAD = {
    "XAU/USD": 0.80,
    "NAS100":  4.0,
    "US500":   2.0,
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
# WATCHDOG & LOG ROTATION
# ============================================================
def watchdog():
    try:
        with open("heartbeat.txt", "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        log.error(f"Watchdog failure: {e}")

def rotate_log():
    file_path = "signals_log.csv"
    if os.path.isfile(file_path):
        if os.path.getsize(file_path) > 5_000_000:
            os.rename(file_path, f"signals_log_{int(time.time())}.csv")

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
                timeout=10
            )
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

def duplicate_signal(symbol_key, direction):
    now = time.time()
    if (
        _last_signal_direction.get(symbol_key) == direction
        and now - _last_signal_time.get(symbol_key, 0) < 5400  # changed from 7200
    ):
        log.info(f"Duplicate signal blocked for {symbol_key}")
        return True
    _last_signal_direction[symbol_key] = direction
    _last_signal_time[symbol_key]      = now
    return False

def economic_news_block():
    return False

# ============================================================
# SESSION FILTER — London + NY+London only (NY alone blocked)
# ============================================================
def in_session(symbol_key):
    h = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]

    if not (s <= h < e):
        return False, "Closed"

    if h < 7:
        return False, "Asian"

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

def get_entry_data(symbol_key):
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

def detect_liquidity_sweep(df):
    """Detects price sweeping a prior swing high/low and reversing."""
    if len(df) < 4:
        return False, False

    prev_high = max(df["high"].tail(4).iloc[:-1])
    prev_low  = min(df["low"].tail(4).iloc[:-1])
    last      = df.iloc[-1]

    bearish_sweep = (
        float(last["high"]) > prev_high
        and float(last["close"]) < prev_high
    )

    bullish_sweep = (
        float(last["low"]) < prev_low
        and float(last["close"]) > prev_low
    )

    return bullish_sweep, bearish_sweep

# ============================================================
# ELITE REVERSAL DETECTION
# ============================================================
def detect_reversal(df, symbol_key):
    """Elite institutional reversal detection."""
    if len(df) < 5:
        return False, False

    last = df.iloc[-1]
    prev = df.iloc[-2]

    rsi        = float(last["rsi"])
    adx        = float(last["adx"])
    high_break = float(last["high"]) > float(prev["high"])
    low_break  = float(last["low"])  < float(prev["low"])
    close      = float(last["close"])
    prev_close = float(prev["close"])

    bull_sweep, bear_sweep = detect_liquidity_sweep(df)

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

    bull_fvg,   bear_fvg   = fair_value_gap(df)
    bull_choch, bear_choch = detect_choch(df)
    bull_rev,   bear_rev   = detect_reversal(df, symbol_key)
    bull_sweep, bear_sweep = detect_liquidity_sweep(df)

    bullish_break = float(last["close"]) > float(df.iloc[-2]["high"]) + atr * 0.12
    bearish_break = float(last["close"]) < float(df.iloc[-2]["low"])  - atr * 0.12

    buy = {
        "HTF":      trend == "BULL",
        "EMA":      ema9 > ema21 > ema50 > ema200,
        "RSI":      56 <= rsi <= 72,                   # loosened from 58-70
        "ADX":      adx > ADX_THRESHOLD,
        "VOL":      volma > 0 and vol > volma * VOL_MULT,
        "FVG":      bull_fvg,
        "CHOCH":    bull_choch,
        "BOS":      bullish_break,
        "REVERSAL": bull_rev,
        "SWEEP":    bull_sweep,
    }

    sell = {
        "HTF":      trend == "BEAR",
        "EMA":      ema9 < ema21 < ema50 < ema200,
        "RSI":      28 <= rsi <= 42,                   # loosened from 30-40
        "ADX":      adx > ADX_THRESHOLD,
        "VOL":      volma > 0 and vol > volma * VOL_MULT,
        "FVG":      bear_fvg,
        "CHOCH":    bear_choch,
        "BOS":      bearish_break,
        "REVERSAL": bear_rev,
        "SWEEP":    bear_sweep,
    }

    buy_score  = sum(buy.values())
    sell_score = sum(sell.values())

    if bull_rev:
        buy_score  += REVERSAL_SCORE_BONUS
    if bear_rev:
        sell_score += REVERSAL_SCORE_BONUS

    return buy, sell, buy_score, sell_score

# ============================================================
# LEVELS
# ============================================================
def calc_levels(price, atr, symbol_key, df, direction, reversal_mode):
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

    if reversal_mode:
        rr = 2.0
    else:
        if symbol_key == "XAU/USD":
            rr = 2.8                   # changed from 3.0
        elif symbol_key == "NAS100":
            rr = 2.7
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
        "US500":   3.00,
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
    if spread > MAX_SPREAD[symbol_key] * 0.95:      # loosened from 0.85
        log.info(f"REJECTED {symbol_key} spread {spread:.4f}")
        return

    df    = add_ind(df)
    price = float(df.iloc[-1]["close"])

    if not (MARKETS[symbol_key]["price_lo"] <= price <= MARKETS[symbol_key]["price_hi"]):
        log.info(f"REJECTED {symbol_key} price out of range")
        return

    trend  = get_trend(symbol_key)
    regime = detect_market_regime(df)

    buy, sell, buy_score, sell_score = build_score(df, trend, symbol_key)

    rsi = float(df.iloc[-1]["rsi"])
    adx = float(df.iloc[-1]["adx"])
    atr = float(df.iloc[-1]["atr"])
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

    if regime == "RANGE" and best < RANGE_MIN_SCORE:
        log.info(f"REJECTED {symbol_key} RANGE score {best} < {RANGE_MIN_SCORE}")
        return

    if regime in ["TREND", "BREAKOUT"] and best < TREND_MIN_SCORE:
        log.info(f"REJECTED {symbol_key} TREND score {best} < {TREND_MIN_SCORE}")
        return

    if reversal_mode and best < REVERSAL_MIN_SCORE:
        log.info(f"REJECTED {symbol_key} reversal score {best} < {REVERSAL_MIN_SCORE}")
        return

    if trend == "BULL" and direction == "SELL" and not reversal_mode:
        log.info(f"REJECTED {symbol_key} countertrend SELL without reversal")
        return

    if trend == "BEAR" and direction == "BUY" and not reversal_mode:
        log.info(f"REJECTED {symbol_key} countertrend BUY without reversal")
        return

    if duplicate_signal(symbol_key, direction):
        return

    now = time.time()
    if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
        remaining = int(SIGNAL_COOLDOWN - (now - _signal_sent[symbol_key]))
        log.info(f"REJECTED {symbol_key} cooldown {remaining}s")
        return

    _signal_sent[symbol_key] = now

    sl, tp, sl_dist, rr = calc_levels(price, atr, symbol_key, df, direction, reversal_mode)
    lot                  = lot_for_risk(price, sl, symbol_key)
    timeframe            = REGIME_TIMEFRAME.get(regime, "1H / 4H")
    signal_type          = "REVERSAL" if reversal_mode else "CONTINUATION"

    log_signal(symbol_key, direction, best, rr, price, sl, tp,
               session, regime, timeframe, signal_type)
    sync_real_pnl()

    checks    = buy if direction == "BUY" else sell
    cond_text = "\n".join([f" {k}" for k, v in checks.items() if v])

    action_emoji = "📈" if direction == "BUY" else "📉"
    type_emoji   = "🔄" if reversal_mode else "🚀"

    msg = (
        f"🎯 *{SYSTEM_VERSION}*\n"
        f"*{MARKETS[symbol_key]['mt5']}* | ⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n\n"
        f"🔥 *Action:* {direction} {action_emoji}\n"
        f"{type_emoji} *Signal Type:* {signal_type}\n"
        f"⭐ *Score:* {best}/10\n"
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
        f"🇺🇸 US500\n\n"
        f"🔄 Reversal + Continuation Engine Active\n"
        f"🛡 Curated Institutional Entry Active\n"
        f"⚡ Global Elite Pro+ Curated Mode"
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
