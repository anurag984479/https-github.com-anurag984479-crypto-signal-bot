# ============================================================
# PEPPERSTONE MOMENTUM HUNTER v20.0
# ULTIMATE 360° INSTITUTIONAL PRECISION ENGINE
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

SYSTEM_VERSION = "v20.0-ULTIMATE-360-INSTITUTIONAL"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v20.0")

TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

# ============================================================
# MARKETS — 5 markets
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

# ============================================================
# SETTINGS
# ============================================================
ATR_MULT               = 0.45
VOL_MULT               = 1.10
ADX_THRESHOLD          = 22
SIGNAL_COOLDOWN        = 1200
HTF_REFRESH            = 1200
MAX_DAILY_LOSS         = -300
MAX_CONSECUTIVE_LOSSES = 4
MIN_SCORE              = 6

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


# ============================================================
# TELEGRAM WITH RETRY
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
# SAFETY GUARDS
# ============================================================
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


def get_spread(df):
    if df is None or len(df) < 3:
        return 999
    recent    = df.tail(3)
    avg_range = (
        recent["high"].astype(float) - recent["low"].astype(float)
    ).mean()
    return avg_range * 0.18


MAX_SPREAD = {
    "XAU/USD": 0.80,
    "XAG/USD": 0.08,
    "BTC/USD": 60,
    "NAS100":  4.0,
    "US500":   2.0,
}


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
        lower_wick > body * 1.8,
        upper_wick > body * 1.8
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

    bull_fvg,   bear_fvg   = fair_value_gap(df)
    bull_choch, bear_choch = detect_choch(df)
    bull_wick,  bear_wick  = rejection_wick(df)

    bias = MARKETS[symbol_key].get("bias", "NEUTRAL")

    buy = {
        "HTF":   trend == "BULL",
        "EMA":   ema9 > ema21 > ema50,
        "RSI":   rsi > 58,
        "ADX":   adx > ADX_THRESHOLD,
        "VOL":   volma > 0 and vol > volma * VOL_MULT,
        "FVG":   bull_fvg,
        "CHOCH": bull_choch,
        "WICK":  bull_wick,
    }

    sell = {
        "HTF":   trend == "BEAR",
        "EMA":   ema9 < ema21 < ema50,
        "RSI":   rsi < 42,
        "ADX":   adx > ADX_THRESHOLD,
        "VOL":   volma > 0 and vol > volma * VOL_MULT,
        "FVG":   bear_fvg,
        "CHOCH": bear_choch,
        "WICK":  bear_wick,
    }

    buy_score  = sum(buy.values())
    sell_score = sum(sell.values())

    # May 2026 bull bias
    if bias == "BULL":
        buy_score  = int(round(buy_score  * 1.10))
        sell_score = int(round(sell_score * 0.90))

    return buy, sell, buy_score, sell_score


# ============================================================
# LEVELS
# ============================================================
def calc_levels(price, direction, atr, symbol_key):
    min_sl   = MARKETS[symbol_key]["min_sl"]
    decimals = MARKETS[symbol_key]["decimals"]

    sl_dist = max(min_sl, atr * ATR_MULT)

    if symbol_key == "BTC/USD":
        sl_dist *= 1.55
    elif symbol_key == "XAU/USD":
        sl_dist *= 1.15
    elif symbol_key == "XAG/USD":
        sl_dist *= 1.10
    elif symbol_key in ["NAS100", "US500"]:
        sl_dist *= 1.08

    if direction == "BUY":
        sl = price - sl_dist
        tp = price + sl_dist * 3
    else:
        sl = price + sl_dist
        tp = price - sl_dist * 3

    return (
        round(sl, decimals),
        round(tp, decimals),
        round(sl_dist, decimals)
    )


# ============================================================
# LOT SIZE
# ============================================================
def lot_for_risk(price, sl, risk):
    sl_dist = abs(price - sl)
    if sl_dist == 0:
        return 0.01
    return max(round(risk / sl_dist, 3), 0.01)


# ============================================================
# SIGNAL JOURNAL
# ============================================================
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

    buy, sell, buy_score, sell_score = build_score(df, trend, symbol_key)

    best = max(buy_score, sell_score)

    log.info(
        f"{symbol_key} | BUY: {buy_score} | SELL: {sell_score} | "
        f"Trend: {trend} | Session: {session}"
    )

    if best < MIN_SCORE:
        log.info(f"REJECTED {symbol_key} score {best} < {MIN_SCORE}")
        return

    if buy_score == sell_score:
        log.info(f"REJECTED {symbol_key} tied score")
        return

    direction = "BUY" if buy_score > sell_score else "SELL"

    # bull market sell guard
    bias = MARKETS[symbol_key].get("bias", "NEUTRAL")
    if bias == "BULL" and direction == "SELL":
        if best < MIN_SCORE + 2:
            log.info(f"REJECTED {symbol_key} SELL — bull bias")
            return

    if duplicate_signal(symbol_key, direction):
        return

    now = time.time()
    if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
        remaining = int(SIGNAL_COOLDOWN - (now - _signal_sent[symbol_key]))
        log.info(f"REJECTED {symbol_key} cooldown {remaining}s")
        return

    _signal_sent[symbol_key] = now

    atr    = float(df.iloc[-1]["atr"])
    rsi    = float(df.iloc[-1]["rsi"])
    adx    = float(df.iloc[-1]["adx"])
    regime = detect_market_regime(df)
    dec    = MARKETS[symbol_key]["decimals"]

    sl, tp, sl_dist = calc_levels(price, direction, atr, symbol_key)

    rr = round(abs(tp - price) / abs(price - sl), 2) if abs(price - sl) > 0 else 0

    if rr < 2.0:
        log.info(f"REJECTED {symbol_key} RR {rr} < 2.0")
        return

    lot = lot_for_risk(price, sl, 25)

    log_signal(symbol_key, direction, best, rr, price, sl, tp, session, regime)
    sync_real_pnl()

    checks    = buy if direction == "BUY" else sell
    cond_text = "\n".join([f" {k}" for k, v in checks.items() if v])

    msg = (
        f"🎯 *{SYSTEM_VERSION}*\n"
        f"*{MARKETS[symbol_key]['mt5']}* | ⭐⭐⭐⭐⭐ {MARKETS[symbol_key]['tier']}\n\n"
        f"🔥 *Action:* {'BUY 📈' if direction == 'BUY' else 'SELL 📉'}\n"
        f"⭐ *Score:* {best}/8\n"
        f"🧠 *Regime:* {regime}\n"
        f"📊 *Market Bias:* {bias}\n\n"
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
        f"⚡ *STRICT ELITE INSTITUTIONAL TVM MODE*"
    )

    send_telegram(msg)

    log.info(
        f"SIGNAL SENT {symbol_key} {direction} | "
        f"Entry: {price} | SL: {sl} | TP: {tp} | RR: {rr}"
    )


# ============================================================
# MAIN
# ============================================================
def main():
    log.info(f"{SYSTEM_VERSION} STARTED")
    send_telegram(
        f"🚀 *{SYSTEM_VERSION} LIVE*\n\n"
        f"📊 *Markets Active:*\n"
        f"₿  BTC/USD\n"
        f"🥇 XAU/USD\n"
        f"🥈 XAG/USD\n"
        f"📈 NAS100\n"
        f"🇺🇸 US500\n\n"
        f"⚡ All systems active"
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
