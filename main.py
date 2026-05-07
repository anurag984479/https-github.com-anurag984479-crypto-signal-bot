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
# PEPPERSTONE ADAPTIVE BOT v14.0 — REAL WORLD
# Structure identical to v8.1, upgraded with:
# - Adaptive strategy switching
# - Structural SLs
# - Fixed 1:3 R:R
# - Breakeven alerts
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v14.0")

TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

DOLLAR_PER_LOT = {
    "XAU/USD": 100.0,
    "BTC/USD": 1.0,
    "GBP/USD": 100000.0,
    "ETH/USD": 1.0,
    "US500":   10.0,
}

MARKETS = {
    "XAU/USD": {"mt5":"XAUUSD.Qraw","yf":"GC=F","price_lo":4000,"price_hi":5500,"sessions":[7,20],"tier":"⭐⭐⭐⭐⭐ Gold #1","decimals":2,"min_sl":25.0,"win_rate":"72%","chart":"https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AXAUUSD&interval=15"},
    "BTC/USD": {"mt5":"BTCUSD.Qraw","yf":None,"price_lo":50000,"price_hi":200000,"sessions":[0,23],"tier":"⭐⭐⭐⭐⭐ BTC #2","decimals":2,"min_sl":500.0,"win_rate":"68%","chart":"https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3ABTCUSD&interval=15"},
    "GBP/USD": {"mt5":"GBPUSD.Qraw","yf":"GBPUSD=X","price_lo":1.10,"price_hi":1.60,"sessions":[7,20],"tier":"⭐⭐⭐⭐ GBP #3","decimals":5,"min_sl":0.0030,"win_rate":"68%","chart":"https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AGBPUSD&interval=15"},
    "ETH/USD": {"mt5":"ETHUSD.Qraw","yf":None,"price_lo":1000,"price_hi":10000,"sessions":[0,23],"tier":"⭐⭐⭐⭐ ETH #4","decimals":2,"min_sl":25.0,"win_rate":"66%","chart":"https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AETHUSD&interval=15"},
    "US500":   {"mt5":"US500.Qraw","yf":"^GSPC","price_lo":5000,"price_hi":10000,"sessions":[13,21],"tier":"⭐⭐⭐⭐ SPX #5","decimals":2,"min_sl":20.0,"win_rate":"66%","chart":"https://www.tradingview.com/chart/?symbol=PEPPERSTONE%3AUS500&interval=15"},
}

SYMBOLS           = list(MARKETS.keys())
RSI_OB            = 65
RSI_OS            = 35
VOL_MULT          = 1.2
RR                = 3   # Fixed 1:3 R:R
SIGNAL_COOLDOWN   = 1800
CONFIRM_THRESHOLD = 3
PRESIG_COOLDOWN   = 600
ADX_THRESHOLD     = 22
HTF_REFRESH       = 3600

_signal_sent = {s: 0 for s in SYMBOLS}
_presig_sent = {s: 0 for s in SYMBOLS}
_htf_cache   = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}

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
        else:
            log.warning(f"Telegram {r.status_code}")
        time.sleep(1)
    except Exception as e:
        log.error(f"Telegram error: {e}")

def breakeven_alert(symbol_key, entry, tp, decimals):
    msg = f"""
⚠️ Breakeven Trigger — {symbol_key}
──────────────────────────────
Trade tightened to breakeven.
📍 Entry: {entry:.{decimals}f}
🛑 SL moved to: {entry:.{decimals}f} (breakeven)
🎯 TP remains: {tp:.{decimals}f} (1:3 target)
"""
    send_telegram(msg)

# ─────────────────────────────────────────────
# FETCH DATA
# ─────────────────────────────────────────────
def fetch_yf(ticker, period, interval):
    try:
        raw = yf.download(ticker, period=period,
                          interval=interval, progress=False,
                          auto_adjust=True)
        if raw.empty:
            raise ValueError(f"Empty {ticker}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [str(c).lower() for c in raw.columns]
        for c in ["open","high","low","close","volume"]:
            if c not in raw.columns:
                raw[c] = 0.0
        return raw[["open","high","low","close","volume"]].copy().reset_index(drop=True)
    except Exception as e:
        log.error(f"Data fetch error {ticker}: {e}")
        return None

# ─────────────────────────────────────────────
# INDICATORS + CONDITIONS
# ─────────────────────────────────────────────
def add_ind(df):
    cl   = pd.to_numeric(df["close"])
    hi   = pd.to_numeric(df["high"])
    lo   = pd.to_numeric(df["low"])
    vol  = pd.to_numeric(df["volume"])
    df["rsi"]   = ta.momentum.RSIIndicator(cl, 14).rsi()
    df["ema9"]  = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(cl, 50).ema_indicator()
    df["atr"]   = ta.volatility.AverageTrueRange(hi, lo, cl, 14).average_true_range()
    df["adx"]   = ta.trend.ADXIndicator(hi, lo, cl, 14).adx()
    df["volma"] = vol.rolling(20).mean()
    return df

def check_conditions(df, trend):
    last  = df.iloc[-1]
    rsi   = float(last["rsi"])
    ema9  = float(last["ema9"])
    ema21 = float(last["ema21"])
    ema50 = float(last["ema50"])
    vol   = float(last["volume"])
    volma = float(last["volma"])
    close = float(last["close"])
    op    = float(last["open"])
    hi    = float(last["high"])
    lo    = float(last["low"])
    atr   = float(last["atr"])
    adx   = float(last["adx"]) if not pd.isna(last["adx"]) else 0

    body     = abs(close - op)
    rng      = hi - lo if hi - lo > 0 else 0.0001
    body_pct = body / rng
    vol_ok   = vol > volma * VOL_MULT

    buy = {
        "RSI oversold (<35)":       rsi < RSI_OS,
        "EMA9 above EMA21":         ema9 > ema21,
        "Volume spike (1.2x)":      vol_ok,
        "Bullish candle (>50%)":    close > op and body_pct > 0.5,
        "Price above EMA50":        close > ema50,
    }
    sell = {
        "RSI overbought (>65)":     rsi > RSI_OB,
        "EMA9 below EMA21":         ema9 < ema21,
        "Volume spike (1.2x)":      vol_ok,
        "Bearish candle (>50%)":    close < op and body_pct > 0.5,
        "Price below EMA50":        close < ema50,
    }

    buy_score  = sum(buy.values())
    sell_score = sum(sell.values())

    if trend == "BULL":
        buy_score  += 1
        sell_score  = 0
    if trend == "BE
