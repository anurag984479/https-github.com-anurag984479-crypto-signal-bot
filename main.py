# ═══════════════════════════════════════════════════════════════
# PEPPERSTONE MOMENTUM HUNTER v14.0 — ELITE 4 MARKET EDITION
# 15m HTF Bias + 5m Entry
# Markets:
# 🥇 Gold (XAU/USD)
# 🥈 Silver (XAG/USD)
# 🥉 BTC/USD
# 🏅 NAS100
# Strict premium A+ setups only
# Railway-ready + Telegram + enhanced logging
# ═══════════════════════════════════════════════════════════════

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
log = logging.getLogger("v14.0")


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
        "price_lo": 50000,
        "price_hi": 200000,
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
RR = 2.0
ATR_MULT = 0.28
VOL_MULT = 1.15
ADX_THRESHOLD = 22
CONFIRM_THRESHOLD = 6
SIGNAL_COOLDOWN = 1200
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

    if not (s <= h < e):
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
        for src in ["coinbase", "binance"]:
            pair = "BTC/USDT" if src == "binance" else "BTC/USD"

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
def add_ind(df):
    df = df.copy()

    cl = pd.to_numeric(df["close"])
    hi = pd.to_numeric(df["high"])
    lo = pd.to_numeric(df["low"])
    vol = pd.to_numeric(df["volume"])

    df["ema9"] = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(cl, 50).ema_indicator()

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

    df = get_htf(symbol_key)

    if df is None or len(df) < 50:
        return "NEUTRAL"

    df = add_ind(df)
    last = df.iloc[-1]

    if last["ema21"] > last["ema50"]:
        trend = "BULL"
    elif last["ema21"] < last["ema50"]:
        trend = "BEAR"
    else:
        trend = "NEUTRAL"

    cache["trend"] = trend
    cache["ts"] = now

    return trend


# ═══════════════════════════════════════════════════════════════
# CONDITIONS
# ═══════════════════════════════════════════════════════════════
def check_conditions(df, trend):
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

    bullish_break = close > df.iloc[-2]["high"]
    bearish_break = close < df.iloc[-2]["low"]

    buy = {
        "HTF Bull": trend == "BULL",
        "EMA Alignment": ema9 > ema21 > ema50,
        "RSI Strength": rsi > 50,
        "Strong Volume": vol_ok,
        "Bull Candle": close > op and strong_body,
        "EMA Pullback": near_ema,
        "BOS": bullish_break,
        "ADX": adx > ADX_THRESHOLD,
    }

    sell = {
        "HTF Bear": trend == "BEAR",
        "EMA Alignment": ema9 < ema21 < ema50,
        "RSI Weakness": rsi < 50,
        "Strong Volume": vol_ok,
        "Bear Candle": close < op and strong_body,
        "EMA Pullback": near_ema,
        "BOS": bearish_break,
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

    sl_dist = max(min_sl, min(atr_sl, swing))
    

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
def lot_for_risk(price, sl, symbol_key, risk=50):
    sl_dist = abs(price - sl)

    if sl_dist == 0:
        return 0.01

    dpl = DOLLAR_PER_LOT[symbol_key]
    return max(round(risk / (sl_dist * dpl), 3), 0.01)


# ═══════════════════════════════════════════════════════════════
# PROCESS
# ═══════════════════════════════════════════════════════════════
def process(symbol_key):
    log.info(f"🔍 Scanning {symbol_key}")

    ok, session = in_session(symbol_key)

    if not ok:
        return

    df, source = get_entry_data(symbol_key)

    if df is None or len(df) < 100:
        return

    df = add_ind(df)
    price = float(df.iloc[-1]["close"])

    if not (
        MARKETS[symbol_key]["price_lo"] <= price <= MARKETS[symbol_key]["price_hi"]
    ):
        return

    trend = get_trend(symbol_key)

    buy, sell, buy_score, sell_score, rsi, close, atr, adx = check_conditions(df, trend)

    best = max(buy_score, sell_score)
    log.info(f"{symbol_key} | Buy Score: {buy_score} | Sell Score: {sell_score} | Best: {best}")

    if adx < ADX_THRESHOLD:
        log.info(f"❌ {symbol_key} rejected due to weak ADX: {adx:.1f}")
        return

    if best < CONFIRM_THRESHOLD:
        return

    now = time.time()

    if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
        log.info(f"⏳ {symbol_key} cooldown active")
        return

    direction = "BUY" if buy_score > sell_score else "SELL"
    checks = buy if direction == "BUY" else sell

    sl, tp, sl_dist = calc_levels(price, direction, atr, symbol_key, df)
    lot = lot_for_risk(price, sl, symbol_key, 50)

    _signal_sent[symbol_key] = now

    mt5 = MARKETS[symbol_key]["mt5"]
    dec = MARKETS[symbol_key]["decimals"]

    msg = f'''
🚀 *A+ SIGNAL — {mt5}* 🚀
_{MARKETS[symbol_key]["tier"]}_

🔥 *Action:* {"BUY 📈" if direction == "BUY" else "SELL 📉"}
⭐ *Score:* {best}/8

📍 *Entry:* ${price:,.{dec}f}
🛑 *SL:* ${sl:,.{dec}f}
🎯 *TP:* ${tp:,.{dec}f} *(1:2 RR)*

📈 *RSI:* {rsi:.1f}
📉 *ADX:* {adx:.1f}
🌍 *HTF:* {trend}
⏰ *Session:* {session}
📡 *Source:* {source}

💵 *$50 Risk Lot:* {lot:.3f}

✅ *A+ Conditions:*
''' + "\n".join(
        [f" ✅ {k}" for k, v in checks.items() if v]
    ) + "\n\n⚡ *STRICT ELITE SETUP ONLY*"

    send_telegram(msg)
    log.info(f"🚀 A+ SIGNAL {symbol_key} {direction}")


# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════
def main():
    log.info("═" * 60)
    log.info("🚀 MOMENTUM HUNTER v14.0 STARTED")
    log.info("🎯 A+ FILTER ONLY | STRICT ELITE MODE")
    log.info("📊 15m HTF + 5m Entry")
    log.info("🥇 Gold | 🥈 Silver | 🥉 BTC | 🏅 NAS100 | 🇺🇸 US500")
    log.info("═" * 60)

    send_telegram("🚀 Bot started successfully on Railway")

    while True:
        try:
            log.info("🔄 Running market scan cycle...")

            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [ex.submit(process, s) for s in SYMBOLS]

                for f in as_completed(futures):
                    pass

            log.info("⏱ Waiting 20s for next cycle...")
            time.sleep(20)

        except Exception as e:
            log.error(f"Main loop error: {e}")
            time.sleep(15)


if __name__ == "__main__":
    main()
