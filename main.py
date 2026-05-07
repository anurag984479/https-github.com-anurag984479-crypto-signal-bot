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
# PEPPERSTONE INSTITUTIONAL FRAMEWORK v14.0 — GLOBAL ADAPTIVE
# Strategy: 15m sniper + 1h/4h bias
# Features: Liquidity sweeps, Order Blocks, FVG, Killzones
# SL      : Dynamic ATR × 2 (min SL per symbol)
# Target  : Fixed 1:2 R:R
# Trades  : 2–6 per day (lower frequency, higher confluence)
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
    "XAU/USD": {"mt5":"XAUUSD.Qraw","yf":"GC=F","min_sl":25.0,"sessions":[7,20],"decimals":2},
    "BTC/USD": {"mt5":"BTCUSD.Qraw","yf":None,"min_sl":500.0,"sessions":[0,23],"decimals":2},
    "GBP/USD": {"mt5":"GBPUSD.Qraw","yf":"GBPUSD=X","min_sl":0.0030,"sessions":[7,20],"decimals":5},
    "ETH/USD": {"mt5":"ETHUSD.Qraw","yf":None,"min_sl":25.0,"sessions":[0,23],"decimals":2},
    "US500":   {"mt5":"US500.Qraw","yf":"^GSPC","min_sl":20.0,"sessions":[13,21],"decimals":2},
}

SYMBOLS           = list(MARKETS.keys())
RSI_OB            = 65
RSI_OS            = 35
VOL_MULT          = 1.2
RR                = 2
SIGNAL_COOLDOWN   = 1800
CONFIRM_THRESHOLD = 3
PRESIG_COOLDOWN   = 600
ADX_THRESHOLD     = 22
HTF_REFRESH       = 3600
ATR_MULT          = 2.0

_signal_sent = {s: 0 for s in SYMBOLS}
_presig_sent = {s: 0 for s in SYMBOLS}
_htf_cache   = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}

# TELEGRAM
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

# LOT SIZE
def lot_table(price, sl, symbol_key):
    sl_dist = abs(price - sl)
    if sl_dist == 0: return "N/A"
    dpl   = DOLLAR_PER_LOT.get(symbol_key, 1.0)
    lines = []
    for risk in [10, 25, 50, 100, 200]:
        lot = round(risk / (sl_dist * dpl), 3)
        if lot < 0.01: lot = 0.01
        lines.append(f"  💵 ${risk:>3} risk → {lot:.3f} lots")
    return "\n".join(lines)

def lot_for_risk(price, sl, symbol_key, risk_usd):
    sl_dist = abs(price - sl)
    if sl_dist == 0: return 0.01
    dpl = DOLLAR_PER_LOT.get(symbol_key, 1.0)
    return max(round(risk_usd / (sl_dist * dpl), 3), 0.01)

# SESSION
def in_session(symbol_key):
    h    = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]
    if not (s <= h < e): return False, "Closed"
    if 12 <= h < 16: return True, "NY+London 🔥🔥"
    if 7  <= h < 12: return True, "London 🔥"
    if h  < 7:       return True, "Asian"
    return True, "New York 🇺🇸"

# DATA FETCH
def fetch_yf(ticker, period, interval):
    raw = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    if raw.empty: return None
    raw.columns = [c.lower() for c in raw.columns]
    return raw[["open","high","low","close","volume"]].reset_index(drop=True)

def get_15m(symbol_key):
    yf_sym = MARKETS[symbol_key]["yf"]
    if yf_sym: return fetch_yf(yf_sym,"15d","15m"), "yf"
    return None, None

def get_htf(symbol_key, tf="1h"):
    yf_sym = MARKETS[symbol_key]["yf"]
    if yf_sym: return fetch_yf(yf_sym,"60d",tf)
    return None

# HTF TREND (1h + 4h EMA50/200)
def get_trend(symbol_key):
    cache = _htf_cache[symbol_key]
    now   = time.time()
    if now - cache["ts"] > HTF_REFRESH:
        df1 = get_htf(symbol_key,"1h")
        df4 = get_htf(symbol_key,"4h")
        if df1 is not None and len(df1)>200 and df4 is not None and len(df4)>200:
            cl1 = pd.to_numeric(df1["close"])
            cl4 = pd.to_numeric(df4["close"])
            e50_1 = ta.trend.EMAIndicator(cl1,50).ema_indicator().iloc[-1]
            e200_1= ta.trend.EMAIndicator(cl1,200).ema_indicator().iloc[-1]
            e50_4 = ta.trend.EMAIndicator(cl4,50).ema_indicator().iloc[-1]
            e200_4= ta.trend.EMAIndicator(cl4,200).ema_indicator().iloc[-1]
            if e50_1>e200_1 and e50_4>e200_4: cache["trend"]="BULL"
            elif e50_1<e200_1 and e50_4<e200_4: cache["trend"]="BEAR"
            else: cache["trend"]="NEUTRAL"
        cache["ts"]=now
        log.info(f"HTF {MARKETS[symbol_key]['mt5']}: {cache['trend']}")
    return cache["trend"]

# INDICATORS + Institutional Filters
def add_ind(df):
    cl   = pd.to_numeric(df["close"])
    hi   = pd.to_numeric(df["high"])
    lo   = pd.to_numeric(df["low"])
    vol  = pd.to_numeric(df["volume"])
    df["rsi"]   = ta.momentum.RSIIndicator(cl,14).rsi()
    df["ema9"]  = ta.trend.EMAIndicator(cl,9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(cl,21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(cl,50).ema_indicator()
    df["atr"]   = ta.volatility.AverageTrueRange(hi,lo,cl,14).average_true_range()
    df["adx"]   = ta.trend.ADXIndicator(hi,lo,cl,14).adx()
    df["volma"] = vol.rolling(20).mean()
    return df

def detect_liquidity_sweep(df): 
    return df["low"].iloc[-1]<df["low"].iloc[-5:].min() or df["high"].iloc[-1]>df["high"].iloc[-5:].max()

def detect_order_block(df): 
    return abs(df["close"].iloc[-1]-df["open"].iloc[-1])<df["atr"].iloc[-1]

def detect_fvg(df): 
    return abs(df["close"].iloc[-1]-df["open"].iloc[-1])>df["atr"].iloc[-1]

def detect_big_bar(df): 
    return (df["high"].iloc[-1]-df["low"].iloc[-1])
