# ============================================================
# PEPPERSTONE ELITE STOCKBURNER HYBRID BOT v10.0
# RR = 2.0 EASY WIN MODE
# Target: 85–90% WR
# Style : Institutional sniper
# Entry : 15m only
# Features:
# ✅ Big Bar Detection
# ✅ Liquidity Sweep
# ✅ Order Block Entry
# ✅ FVG Confirmation
# ✅ London/NY Killzones
# ✅ EMA Trend Alignment
# ✅ ADX + Volume
# ============================================================

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

# ============================================================
# CONFIG
# ============================================================

TOKEN   = os.getenv(
    "TOKEN",
    "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk"
)

CHAT_ID = os.getenv(
    "CHAT_ID",
    "8783763018"
)

RR                    = 2.0
SIGNAL_COOLDOWN       = 3600
PRESIGNAL_COOLDOWN    = 900
ATR_MULT              = 2.2
ADX_THRESHOLD         = 25
VOL_MULT              = 1.5
PRE_SIGNAL_SCORE      = 5
FULL_SIGNAL_SCORE     = 7
BREAKOUT_BUFFER       = 0.15
HTF_REFRESH           = 3600

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)
log = logging.getLogger("StockBurnerV10")

# ============================================================
# MARKETS
# ============================================================

MARKETS = {
    "XAU/USD": {
        "yf": "GC=F",
        "mt5": "XAUUSD.Qraw",
        "min_sl": 25.0,
        "decimals": 2,
        "tier": "⭐⭐⭐⭐⭐ Gold #1",
        "chart": "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AXAUUSD&interval=15",
    },
    "BTC/USD": {
        "yf": None,
        "mt5": "BTCUSD.Qraw",
        "min_sl": 500.0,
        "decimals": 2,
        "tier": "⭐⭐⭐⭐⭐ BTC #2",
        "chart": "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ABTCUSD&interval=15",
    },
    "ETH/USD": {
        "yf": None,
        "mt5": "ETHUSD.Qraw",
        "min_sl": 25.0,
        "decimals": 2,
        "tier": "⭐⭐⭐⭐ ETH #3",
        "chart": "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AETHUSD&interval=15",
    },
    "GBP/USD": {
        "yf": "GBPUSD=X",
        "mt5": "GBPUSD.Qraw",
        "min_sl": 0.0030,
        "decimals": 5,
        "tier": "⭐⭐⭐⭐ GBP #4",
        "chart": "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AGBPUSD&interval=15",
    },
    "US500": {
        "yf": "^GSPC",
        "mt5": "US500.Qraw",
        "min_sl": 20.0,
        "decimals": 2,
        "tier": "⭐⭐⭐⭐ SPX #5",
        "chart": "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AUS500&interval=15",
    },
}

SYMBOLS = list(MARKETS.keys())

_signal_sent = {s: 0 for s in SYMBOLS}
_presignal_sent = {s: 0 for s in SYMBOLS}
_htf_cache = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}

# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        log.info("✅ Telegram sent")
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ============================================================
# KILLZONE FILTER (IST)
# London: 12:30–14:30
# NY:     18:30–20:30
# ============================================================

def in_killzone():
    now = datetime.now()
    mins = now.hour * 60 + now.minute

    london_start = 12 * 60 + 30
    london_end   = 14 * 60 + 30

    ny_start = 18 * 60 + 30
    ny_end   = 20 * 60 + 30

    return (
        london_start <= mins <= london_end or
        ny_start <= mins <= ny_end
    )

# ============================================================
# DATA FETCH
# ============================================================

def fetch_yf(ticker, period="60d", interval="15m"):
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        progress=False,
        auto_adjust=True
    )

    if df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [c.lower() for c in df.columns]

    return df.reset_index(drop=True)

def fetch_ccxt(exchange, symbol, tf="15m", limit=300):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)

    return pd.DataFrame(
        ohlcv,
        columns=["time","open","high","low","close","volume"]
    )

def get_data(symbol, tf="15m"):
    try:
        if symbol == "BTC/USD":
            return fetch_ccxt(ccxt.coinbase(), "BTC/USD", tf)

        if symbol == "ETH/USD":
            return fetch_ccxt(ccxt.coinbase(), "ETH/USD", tf)

        yf_sym = MARKETS[symbol]["yf"]

        if yf_sym:
            period = "60d" if tf == "15m" else "180d"
            return fetch_yf(yf_sym, period, tf)

    except Exception as e:
        log.error(f"Data fetch error {symbol}: {e}")

    return None

# ============================================================
# INDICATORS
# ============================================================

def add_indicators(df):
    cl = pd.to_numeric(df["close"])
    hi = pd.to_numeric(df["high"])
    lo = pd.to_numeric(df["low"])
    vol = pd.to_numeric(df["volume"])

    df["rsi"] = ta.momentum.RSIIndicator(cl, 14).rsi()
    df["ema9"] = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(cl, 50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(cl, 200).ema_indicator()
    df["atr"] = ta.volatility.AverageTrueRange(
        hi, lo, cl, 14
    ).average_true_range()
    df["adx"] = ta.trend.ADXIndicator(
        hi, lo, cl, 14
    ).adx()
    df["volma"] = vol.rolling(20).mean()

    return df

# ============================================================
# HTF TREND
# ============================================================

def get_trend(symbol):
    cache = _htf_cache[symbol]
    now = time.time()

    if now - cache["ts"] < HTF_REFRESH:
        return cache["trend"]

    df = get_data(symbol, "1h")

    if df is None or len(df) < 200:
        return "NEUTRAL"

    df = add_indicators(df)

    trend = (
        "BULL"
        if df.iloc[-1]["ema50"] > df.iloc[-1]["ema200"]
        else "BEAR"
    )

    cache["trend"] = trend
    cache["ts"] = now

    return trend

# ============================================================
# STOCKBURNER PATTERNS
# ============================================================

def big_bar(df):
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    rng = max(last["high"] - last["low"], 0.0001)

    return (body / rng) > 0.60

def liquidity_sweep(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    sweep_high = last["high"] > prev["high"] and last["close"] < prev["high"]
    sweep_low = last["low"] < prev["low"] and last["close"] > prev["low"]

    return sweep_high, sweep_low

def fair_value_gap(df):
    if len(df) < 3:
        return False, False

    c1 = df.iloc[-3]
    c3 = df.iloc[-1]

    bullish_fvg = c3["low"] > c1["high"]
    bearish_fvg = c3["high"] < c1["low"]

    return bullish_fvg, bearish_fvg

def order_block(df):
    prev = df.iloc[-2]

    bullish_ob = prev["close"] < prev["open"]
    bearish_ob = prev["close"] > prev["open"]

    return bullish_ob, bearish_ob

# ============================================================
# LEVELS
# ============================================================

def calc_levels(price, direction, atr, symbol, df):
    min_sl = MARKETS[symbol]["min_sl"]

    recent_high = df["high"].tail(12).max()
    recent_low = df["low"].tail(12).min()

    sl_buffer = max(atr * ATR_MULT, min_sl)

    if direction == "BUY":
        sl = recent_low - sl_buffer * 0.25
        tp = price + ((price - sl) * RR)
    else:
        sl = recent_high + sl_buffer * 0.25
        tp = price - ((sl - price) * RR)

    return sl, tp, abs(price - sl)

# ============================================================
# EVALUATION
# ============================================================

def evaluate(df, trend):
    last = df.iloc[-1]

    bigbar = big_bar(df)

    sweep_high, sweep_low = liquidity_sweep(df)
    bullish_fvg, bearish_fvg = fair_value_gap(df)
    bullish_ob, bearish_ob = order_block(df)

    rsi = float(last["rsi"])
    ema9 = float(last["ema9"])
    ema21 = float(last["ema21"])
    ema50 = float(last["ema50"])
    adx = float(last["adx"])
    atr = float(last["atr"])
    close = float(last["close"])
    open_ = float(last["open"])

    vol_ok = float(last["volume"]) > float(last["volma"]) * VOL_MULT

    breakout_buy = close > ema21 + atr * BREAKOUT_BUFFER
    breakout_sell = close < ema21 - atr * BREAKOUT_BUFFER

    buy = {
        "Killzone": in_killzone(),
        "Big bar": bigbar,
        "Liquidity sweep low": sweep_low,
        "Bullish order block": bullish_ob,
        "Bullish FVG": bullish_fvg,
        "EMA alignment": ema9 > ema21,
        "Trend filter": close > ema50,
        "ADX strong": adx > ADX_THRESHOLD,
        "Volume spike": vol_ok,
        "Breakout": breakout_buy,
    }

    sell = {
        "Killzone": in_killzone(),
        "Big bar": bigbar,
        "Liquidity sweep high": sweep_high,
        "Bearish order block": bearish_ob,
        "Bearish FVG": bearish_fvg,
        "EMA alignment": ema9 < ema21,
        "Trend filter": close < ema50,
        "ADX strong": adx > ADX_THRESHOLD,
        "Volume spike": vol_ok,
        "Breakout": breakout_sell,
    }

    buy_score = sum(buy.values())
    sell_score = sum(sell.values())

    if trend == "BULL":
        buy_score += 1
        sell_score = 0

    if trend == "BEAR":
        sell_score += 1
        buy_score = 0

    return buy, sell, buy_score, sell_score

# ============================================================
# PROCESS
# ============================================================

def process(symbol):
    df = get_data(symbol)

    if df is None or len(df) < 250:
        return

    df = add_indicators(df)

    trend = get_trend(symbol)

    buy, sell, buy_score, sell_score = evaluate(df, trend)

    if buy_score >= sell_score:
        direction = "BUY"
        checks = buy
        score = buy_score
    else:
        direction = "SELL"
        checks = sell
        score = sell_score

    price = float(df.iloc[-1]["close"])
    atr = float(df.iloc[-1]["atr"])

    now = time.time()

    # PRE ALERT
    if PRE_SIGNAL_SCORE <= score < FULL_SIGNAL_SCORE:
        if now - _presignal_sent[symbol] > PRESIGNAL_COOLDOWN:
            _presignal_sent[symbol] = now

            send_telegram(
                f"👀 PRE-ALERT — {MARKETS[symbol]['mt5']}\n"
                f"Potential {direction}\n"
                f"⭐ Score: {score}/10\n"
                f"🌍 Trend: {trend}\n"
                f"⚡ Institutional setup building..."
            )

    # FULL SIGNAL
    if score >= FULL_SIGNAL_SCORE:
        if now - _signal_sent[symbol] < SIGNAL_COOLDOWN:
            return

        sl, tp, sl_dist = calc_levels(
            price, direction, atr, symbol, df
        )

        passed = [k for k,v in checks.items() if v]
        failed = [k for k,v in checks.items() if not v]

        _signal_sent[symbol] = now

        msg = (
            f"🚀 SIGNAL — {MARKETS[symbol]['mt5']} 🚀\n"
            f"{MARKETS[symbol]['tier']}\n\n"
            f"🔥 Action: {direction}\n"
            f"⭐ Score: {score}/10\n"
            f"🌍 Trend: {trend}\n\n"
            f"📍 Entry: {price:.{MARKETS[symbol]['decimals']}f}\n"
            f"🛑 SL: {sl:.{MARKETS[symbol]['decimals']}f}\n"
            f"🎯 TP: {tp:.{MARKETS[symbol]['decimals']}f}\n"
            f"⚖️ RR: 1:{RR}\n\n"
            f"✅ Confirmed:\n"
            + "\n".join([f"✅ {x}" for x in passed]) +
            "\n\n❌ Missing:\n"
            + "\n".join([f"❌ {x}" for x in failed]) +
            f"\n\n⚡ STOCKBURNER HYBRID ACTIVE\n"
            f"🔗 {MARKETS[symbol]['chart']}"
        )

        send_telegram(msg)

# ============================================================
# SCAN
# ============================================================

def scan():
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(process, s) for s in SYMBOLS]

        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                log.error(f"Scan error: {e}")

# ============================================================
# MAIN
# ============================================================

def main():
    log.info("🚀 STOCKBURNER HYBRID BOT v10.0 STARTED")

    while True:
        try:
            scan()
            time.sleep(60)

        except KeyboardInterrupt:
            log.info("👋 Bot stopped")
            break

        except Exception as e:
            log.error(f"Main loop error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
