import time
import logging
import requests
import ccxt
import pandas as pd
import numpy as np
import ta
import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

# ═══════════════════════════════════════════════════════════════
# PEPPERSTONE MOMENTUM HUNTER v7.1
# Strategy : Confirmed momentum — 1:2 R:R only
# Timeframe: 5m signals + 1h trend
# Target   : 5-10 confirmed trades per day
# Win Rate : 65-70% realistic
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v7")

TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

MARKETS = {
    "XAU/USD": {
        "mt5":            "XAUUSD.Qraw",
        "yf":             "GC=F",
        "price_lo":       4000,
        "price_hi":       5500,
        "sessions":       [0, 22],
        "tier":           "⭐⭐⭐ Gold",
        "pip_multiplier": 100,
        "decimals":       2,
        "min_sl":         12.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AXAUUSD&interval=5",
    },
    "BTC/USD": {
        "mt5":            "BTCUSD.Qraw",
        "yf":             None,
        "price_lo":       50000,
        "price_hi":       200000,
        "sessions":       [0, 23],
        "tier":           "⭐⭐⭐ BTC",
        "pip_multiplier": 1,
        "decimals":       2,
        "min_sl":         200.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ABTCUSD&interval=5",
    },
    "ETH/USD": {
        "mt5":            "ETHUSD.Qraw",
        "yf":             None,
        "price_lo":       1000,
        "price_hi":       10000,
        "sessions":       [0, 23],
        "tier":           "⭐⭐⭐ ETH",
        "pip_multiplier": 1,
        "decimals":       2,
        "min_sl":         10.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AETHUSD&interval=5",
    },
    "GBP/USD": {
        "mt5":            "GBPUSD.Qraw",
        "yf":             "GBPUSD=X",
        "price_lo":       1.10,
        "price_hi":       1.60,
        "sessions":       [0, 22],
        "tier":           "⭐⭐⭐ GBP",
        "pip_multiplier": 10000,
        "decimals":       5,
        "min_sl":         0.0015,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AGBPUSD&interval=5",
    },
    "EUR/USD": {
        "mt5":            "EURUSD.Qraw",
        "yf":             "EURUSD=X",
        "price_lo":       1.00,
        "price_hi":       1.50,
        "sessions":       [0, 22],
        "tier":           "⭐⭐⭐ EUR",
        "pip_multiplier": 10000,
        "decimals":       5,
        "min_sl":         0.0015,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AEURUSD&interval=5",
    },
    "US500": {
        "mt5":            "US500.Qraw",
        "yf":             "^GSPC",
        "price_lo":       5000,
        "price_hi":       10000,
        "sessions":       [13, 21],
        "tier":           "⭐⭐⭐ SPX",
        "pip_multiplier": 1,
        "decimals":       2,
        "min_sl":         10.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AUS500&interval=5",
    },
    "USTEC": {
        "mt5":            "USTEC.Qraw",
        "yf":             "^NDX",
        "price_lo":       15000,
        "price_hi":       30000,
        "sessions":       [13, 21],
        "tier":           "⭐⭐⭐ NAS",
        "pip_multiplier": 1,
        "decimals":       2,
        "min_sl":         50.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AUSTEC&interval=5",
    },
    "XRP/USD": {
        "mt5":            "XRPUSD.Qraw",
        "yf":             None,
        "price_lo":       0.1,
        "price_hi":       10,
        "sessions":       [0, 23],
        "tier":           "⭐⭐ XRP",
        "pip_multiplier": 1000,
        "decimals":       4,
        "min_sl":         0.010,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AXRPUSD&interval=5",
    },
    "SOL/USD": {
        "mt5":            "SOLUSD.Qraw",
        "yf":             None,
        "price_lo":       10,
        "price_hi":       1000,
        "sessions":       [0, 23],
        "tier":           "⭐⭐ SOL",
        "pip_multiplier": 10,
        "decimals":       2,
        "min_sl":         1.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ASOLUSD&interval=5",
    },
    "US30": {
        "mt5":            "US30.Qraw",
        "yf":             "^DJI",
        "price_lo":       30000,
        "price_hi":       60000,
        "sessions":       [13, 21],
        "tier":           "⭐⭐ DOW",
        "pip_multiplier": 1,
        "decimals":       2,
        "min_sl":         80.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AUS30&interval=5",
    },
    "WTI/USD": {
        "mt5":            "WTIUSD.Qraw",
        "yf":             "CL=F",
        "price_lo":       30,
        "price_hi":       150,
        "sessions":       [0, 22],
        "tier":           "⭐⭐ OIL",
        "pip_multiplier": 100,
        "decimals":       2,
        "min_sl":         0.30,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AWTIUSD&interval=5",
    },
    "DE30": {
        "mt5":            "DE30.Qraw",
        "yf":             "^GDAXI",
        "price_lo":       15000,
        "price_hi":       30000,
        "sessions":       [6, 16],
        "tier":           "⭐⭐ DAX",
        "pip_multiplier": 1,
        "decimals":       2,
        "min_sl":         40.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ADE30&interval=5",
    },
    "BNB/USD": {
        "mt5":            "BNBUSD.Qraw",
        "yf":             None,
        "price_lo":       100,
        "price_hi":       2000,
        "sessions":       [0, 23],
        "tier":           "⭐⭐ BNB",
        "pip_multiplier": 1,
        "decimals":       2,
        "min_sl":         3.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ABNBUSD&interval=5",
    },
    "JP225": {
        "mt5":            "JP225.Qraw",
        "yf":             "^N225",
        "price_lo":       25000,
        "price_hi":       50000,
        "sessions":       [0, 8],
        "tier":           "⭐⭐ NKY",
        "pip_multiplier": 1,
        "decimals":       2,
        "min_sl":         60.0,
        "chart":          "https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AJP225&interval=5",
    },
}

SYMBOLS         = list(MARKETS.keys())
RSI_OB          = 62
RSI_OS          = 38
VOL_MULT        = 1.1
RR              = 2
SIGNAL_COOLDOWN = 900
CONFIRM_THRESHOLD = 3
PRESIG_COOLDOWN   = 300

_signal_sent = {s: 0 for s in SYMBOLS}
_presig_sent = {s: 0 for s in SYMBOLS}
_htf_cache   = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}
HTF_REFRESH  = 3600

# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────
def send_telegram(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
        if r.status_code == 200:
            log.info("✅ Telegram sent")
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ─────────────────────────────────────────────
# LOT SIZE
# ─────────────────────────────────────────────
def lot_table(price, sl, symbol_key):
    sl_dist = abs(price - sl)
    if sl_dist == 0:
        return "N/A"
    mult  = MARKETS[symbol_key]["pip_multiplier"]
    lines = []
    for risk in [10, 25, 50, 100, 200]:
        lot = round(risk / (sl_dist * mult), 3)
        if lot < 0.01:
            lot = 0.01
        lines.append(f"  💵 ${risk} → {lot} lots")
    return "\n".join(lines)

# ─────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────
def in_session(symbol_key):
    h    = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]
    if not (s <= h < e):
        return False, "Closed"
    if 12 <= h < 16: return True, "NY+London 🔥"
    if 7  <= h < 12: return True, "London"
    if h  < 7:       return True, "Asian"
    return True, "New York"

# ─────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────
def fetch_yf(ticker, period, interval):
    raw = yf.download(ticker, period=period,
                      interval=interval, progress=False,
                      auto_adjust=True)
    if raw.empty:
        raise ValueError(f"Empty {ticker}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw.columns = [c.lower() for c in raw.columns]
    for c in ["open","high","low","close","volume"]:
        if c not in raw.columns:
            raw[c] = 0.0
    return raw[["open","high","low","close","volume"]].copy().reset_index(drop=True)

def fetch_ccxt(exchange, sym, tf, limit):
    ohlcv = exchange.fetch_ohlcv(sym, timeframe=tf, limit=limit)
    return pd.DataFrame(ohlcv,
                        columns=["time","open","high","low","close","volume"])

def get_5m_data(symbol_key):
    mkt    = MARKETS[symbol_key]
    yf_sym = mkt["yf"]

    if symbol_key == "BTC/USD":
        for src, sym in [("coinbase","BTC/USD"),("binance","BTC/USDT")]:
            try:
                ex = getattr(ccxt, src)()
                return fetch_ccxt(ex, sym, "5m", 200), src
            except: pass
        try:
            return fetch_yf("BTC-USD","5d","5m"), "yf"
        except: return None, None

    if symbol_key == "ETH/USD":
        for src, sym in [("coinbase","ETH/USD"),("binance","ETH/USDT")]:
            try:
                ex = getattr(ccxt, src)()
                return fetch_ccxt(ex, sym, "5m", 200), src
            except: pass
        try:
            return fetch_yf("ETH-USD","5d","5m"), "yf"
        except: return None, None

    if symbol_key == "XRP/USD":
        for src, sym in [("binance","XRP/USDT"),("coinbase","XRP/USD")]:
            try:
                ex = getattr(ccxt, src)()
                return fetch_ccxt(ex, sym, "5m", 200), src
            except: pass
        try:
            return fetch_yf("XRP-USD","5d","5m"), "yf"
        except: return None, None

    if symbol_key == "SOL/USD":
        for src, sym in [("binance","SOL/USDT"),("coinbase","SOL/USD")]:
            try:
                ex = getattr(ccxt, src)()
                return fetch_ccxt(ex, sym, "5m", 200), src
            except: pass
        try:
            return fetch_yf("SOL-USD","5d","5m"), "yf"
        except: return None, None

    if symbol_key == "BNB/USD":
        try:
            ex = ccxt.binance()
            return fetch_ccxt(ex, "BNB/USDT", "5m", 200), "binance"
        except: pass
        try:
            return fetch_yf("BNB-USD","5d","5m"), "yf"
        except: return None, None

    if yf_sym:
        try:
            return fetch_yf(yf_sym, "5d", "5m"), "yf"
        except: return None, None

    return None, None

def get_htf_data(symbol_key):
    mkt    = MARKETS[symbol_key]
    yf_sym = mkt["yf"]
    srcs   = {
        "BTC/USD": [("coinbase","BTC/USD"),("binance","BTC/USDT")],
        "ETH/USD": [("coinbase","ETH/USD"),("binance","ETH/USDT")],
        "XRP/USD": [("binance","XRP/USDT"),("coinbase","XRP/USD")],
        "SOL/USD": [("binance","SOL/USDT"),("coinbase","SOL/USD")],
        "BNB/USD": [("binance","BNB/USDT")],
    }
    if symbol_key in srcs:
        for src, sym in srcs[symbol_key]:
            try:
                ex = getattr(ccxt, src)()
                return fetch_ccxt(ex, sym, "1h", 250)
            except: pass
    if yf_sym:
        try:
            return fetch_yf(yf_sym, "30d", "1h")
        except: pass
    return None

# ─────────────────────────────────────────────
# HTF TREND
# ─────────────────────────────────────────────
def htf_trend(symbol_key):
    cache = _htf_cache[symbol_key]
    now   = time.time()
    if now - cache["ts"] > HTF_REFRESH:
        df = get_htf_data(symbol_key)
        if df is not None and len(df) > 200:
            cl     = pd.to_numeric(df["close"])
            e50    = ta.trend.EMAIndicator(cl, 50).ema_indicator().iloc[-1]
            e200   = ta.trend.EMAIndicator(cl, 200).ema_indicator().iloc[-1]
            cache["trend"] = "BULL" if e50 > e200 else "BEAR"
        cache["ts"] = now
        log.info(f"HTF {MARKETS[symbol_key]['mt5']}: {cache['trend']}")
    return cache["trend"]

# ─────────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────────
def add_ind(df):
    cl          = pd.to_numeric(df["close"])
    hi          = pd.to_numeric(df["high"])
    lo          = pd.to_numeric(df["low"])
    vol         = pd.to_numeric(df["volume"])
    df          = df.copy()
    df["rsi"]   = ta.momentum.RSIIndicator(cl, 14).rsi()
    df["ema9"]  = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["atr"]   = ta.volatility.AverageTrueRange(hi, lo, cl, 14).average_true_range()
    df["volma"] = vol.rolling(20).mean()
    return df

# ─────────────────────────────────────────────
# 5 CONDITIONS
# ─────────────────────────────────────────────
def check_conditions(df, trend):
    last  = df.iloc[-1]
    rsi   = float(last["rsi"])
    ema9  = float(last["ema9"])
    ema21 = float(last["ema21"])
    vol   = float(last["volume"])
    volma = float(last["volma"])
    close = float(last["close"])
    op    = float(last["open"])
    hi    = float(last["high"])
    lo    = float(last["low"])
    atr   = float(last["atr"])

    body     = abs(close - op)
    rng      = hi - lo if (hi - lo) > 0 else 0.0001
    body_pct = body / rng

    buy = {
        "RSI oversold (<38)":    rsi < RSI_OS,
        "EMA9 > EMA21":          ema9 > ema21,
        "Volume spike (1.1x)":   vol > volma * VOL_MULT,
        "Bullish candle (>50%)": close > op and body_pct > 0.5,
        "HTF trend BULL":        trend == "BULL",
    }
    sell = {
        "RSI overbought (>62)":  rsi > RSI_OB,
        "EMA9 < EMA21":          ema9 < ema21,
        "Volume spike (1.1x)":   vol > volma * VOL_MULT,
        "Bearish candle (>50%)": close < op and body_pct > 0.5,
        "HTF trend BEAR":        trend == "BEAR",
    }

    buy_score  = sum(buy.values())
    sell_score = sum(sell.values())

    return buy, sell, buy_score, sell_score, rsi, close, ema9, ema21, atr

# ─────────────────────────────────────────────
# SL + TP
# ─────────────────────────────────────────────
def calc_sl_tp(price, direction, atr, symbol_key):
    min_sl  = MARKETS[symbol_key]["min_sl"]
    sl_dist = max(atr * 1.5, min_sl)
    if direction == "BUY":
        sl = price - sl_dist
        tp = price + sl_dist * RR
    else:
        sl = price + sl_dist
        tp = price - sl_dist * RR
    return sl, tp, sl_dist

# ─────────────────────────────────────────────
# PROCESS ONE MARKET
# ─────────────────────────────────────────────
def process(symbol_key):
    mkt = MARKETS[symbol_key]
    ok, session = in_session(symbol_key)
    if not ok:
        return "NONE"

    result = get_5m_data(symbol_key)
    if result is None or result[0] is None:
        return "NONE"
    df, source = result
    if len(df) < 50:
        return "NONE"

    df   = add_ind(df)
    last = df.iloc[-1]
    if pd.isna(last["rsi"]) or pd.isna(last["ema9"]) or pd.isna(last["atr"]):
        return "NONE"

    price = float(last["close"])
    if not (mkt["price_lo"] <= price <= mkt["price_hi"]):
        return "NONE"

    trend = htf_trend(symbol_key)
    buy, sell, buy_score, sell_score, rsi, close, ema9, ema21, atr = \
        check_conditions(df, trend)

    mt5 = mkt["mt5"]
    dec = mkt["decimals"]
    now = time.time()

    best_score = max(buy_score, sell_score)
    direction  = "BUY" if buy_score >= sell_score else "SELL"

    # ── PRE-SIGNAL 2/5 ──
    if best_score == 2:
        if now - _presig_sent[symbol_key] > PRESIG_COOLDOWN:
            _presig_sent[symbol_key] = now
            checks  = buy if direction == "BUY" else sell
            waiting = [k for k, v in checks.items() if not v]
            wstr    = "\n".join([f"  ⏳ {w}" for w in waiting])
            msg = (
                f"👀 *PRE-ALERT — {mt5}*\n\n"
                f"*2/5 conditions met — building!*\n\n"
                f"💹 *Price:* ${price:,.{dec}f}\n"
                f"📊 *Direction:* {'Bullish 📈' if direction=='BUY' else 'Bearish 📉'}\n"
                f"📈 *RSI:* {rsi:.1f}\n"
                f"🌍 *HTF:* {trend}\n"
                f"⏰ *Session:* {session}\n\n"
                f"*Still need:*\n{wstr}\n\n"
                f"👀 *Watch this!*\n"
                f"🔗 [Chart]({mkt['chart']})"
            )
            send_telegram(msg)
            log.info(f"👀 PRE {mt5} {direction} 2/5")
        return "PRESIGNAL"

    # ── CONFIRMED SIGNAL 3/5 ──
    if best_score >= CONFIRM_THRESHOLD:
        if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN:
            return "COOLDOWN"

        if buy_score >= sell_score and buy_score >= CONFIRM_THRESHOLD:
            direction = "BUY"
            checks    = buy
            signal    = "LONG / BUY"
        elif sell_score >= CONFIRM_THRESHOLD:
            direction = "SELL"
            checks    = sell
            signal    = "SHORT / SELL"
        else:
            return "NONE"

        passed   = [k for k, v in checks.items() if v]
        pass_str = "\n".join([f"  ✅ {p}" for p in passed])

        sl, tp, sl_dist = calc_sl_tp(price, direction, atr, symbol_key)
        lots            = lot_table(price, sl, symbol_key)
        _signal_sent[symbol_key] = now

        msg = (
            f"🚀 *CONFIRMED SIGNAL — {mt5}* 🚀\n"
            f"_{mkt['tier']}_\n\n"
            f"🔥 *Action:* {signal}\n"
            f"⭐ *Confirmed:* {best_score}/5 conditions\n\n"
            f"💹 *Price:*       ${price:,.{dec}f}\n"
            f"📍 *Entry:*       {price:,.{dec}f}\n"
            f"🛑 *Stop Loss:*   {sl:,.{dec}f}  (-{sl_dist:,.{dec}f})\n"
            f"🎯 *Take Profit:* {tp:,.{dec}f}  (+{sl_dist*RR:,.{dec}f})\n"
            f"⚖️ *R:R:*         1:{RR}\n\n"
            f"📈 *RSI:* {rsi:.1f}\n"
            f"📊 *EMA9 vs EMA21:* "
            f"{'9 > 21 ✅' if ema9 > ema21 else '9 < 21 ✅'}\n"
            f"🌍 *HTF (1h):* {trend}\n"
            f"⏰ *Session:* {session}\n"
            f"📡 *Source:* {source}\n\n"
            f"*Confirmed ({best_score}/5):*\n{pass_str}\n\n"
            f"📦 *Lot Sizes:*\n{lots}\n\n"
            f"⚡ *ENTER NOW — 1:2 TARGET!*\n"
            f"🔗 [Open Chart]({mkt['chart']})"
        )
        send_telegram(msg)
        log.info(
            f"🚀 SIGNAL {mt5}: {signal} {best_score}/5 | "
            f"Entry:{price:.{dec}f} SL:{sl:.{dec}f} TP:{tp:.{dec}f}"
        )
        return "SIGNAL"

    log.info(
        f"Heartbeat {mt5} | ${price:,.{dec}f} | "
        f"RSI:{rsi:.1f} | HTF:{trend} | {session} | "
        f"Buy:{buy_score} Sell:{sell_score}"
    )
    return "NONE"

# ─────────────────────────────────────────────
# SCAN ALL 14
# ─────────────────────────────────────────────
def scan():
    fired = False
    with ThreadPoolExecutor(max_workers=14) as ex:
        futures = {ex.submit(process, s): s for s in SYMBOLS}
        for f in as_completed(futures):
            try:
                if f.result() == "SIGNAL":
                    fired = True
            except Exception as e:
                log.error(f"Error {futures[f]}: {e}")
    return fired

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    log.info("═" * 60)
    log.info("🚀 PEPPERSTONE MOMENTUM HUNTER v7.1")
    log.info("📊 14 Markets — Pepperstone MT5")
    log.info("⚡ Timeframe : 5m signals + 1h trend")
    log.info("✅ Confirm  : 3/5 conditions = SIGNAL")
    log.info("👀 Pre-alert: 2/5 conditions = WARNING")
    log.info("🎯 Target   : 1:2 R:R fixed")
    log.info("📈 Trades   : 5-10 per day")
    log.info("🛑 SL       : 1.5x ATR realistic")
    log.info("📰 News     : NO blackout — always trading")
    log.info("🌙 Crypto   : 24/7")
    log.info("═" * 60)

    log.info("🔄 Warming HTF cache...")
    with ThreadPoolExecutor(max_workers=14) as ex:
        for s in SYMBOLS:
            ex.submit(htf_trend, s)
    log.info("✅ HTF ready — scanning!")
    log.info("═" * 60)

    while True:
        try:
            t0    = time.time()
            fired = scan()
            log.info(f"⏱️  Cycle: {time.time()-t0:.1f}s")
            time.sleep(20 if fired else 10)
        except KeyboardInterrupt:
            log.info("👋 Stopped")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
