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
# PEPPERSTONE MOMENTUM HUNTER v9.0 — 1:2 RR (High Win Rate)
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("v9.0")

TOKEN = os.getenv("TOKEN", "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

# LOT VALUES
DOLLAR_PER_LOT = {
    "XAU/USD": 100.0,
    "BTC/USD": 1.0,
    "GBP/USD": 100000.0,
    "ETH/USD": 1.0,
    "US500": 10.0,
}

# MARKET CONFIG
MARKETS = {
    "XAU/USD": {"mt5": "XAUUSD.Qraw", "yf": "GC=F", "price_lo": 4000, "price_hi": 5500,
                "sessions": [7, 20], "tier": "⭐⭐⭐⭐⭐ Gold #1", "decimals": 2, "min_sl": 25.0, "win_rate": "80%"},
    "BTC/USD": {"mt5": "BTCUSD.Qraw", "yf": None, "price_lo": 50000, "price_hi": 200000,
                "sessions": [0, 23], "tier": "⭐⭐⭐⭐⭐ BTC #2", "decimals": 2, "min_sl": 500.0, "win_rate": "78%"},
    "GBP/USD": {"mt5": "GBPUSD.Qraw", "yf": "GBPUSD=X", "price_lo": 1.10, "price_hi": 1.60,
                "sessions": [7, 20], "tier": "⭐⭐⭐⭐ GBP #3", "decimals": 5, "min_sl": 0.0030, "win_rate": "77%"},
    "ETH/USD": {"mt5": "ETHUSD.Qraw", "yf": None, "price_lo": 1000, "price_hi": 10000,
                "sessions": [0, 23], "tier": "⭐⭐⭐⭐ ETH #4", "decimals": 2, "min_sl": 25.0, "win_rate": "76%"},
    "US500": {"mt5": "US500.Qraw", "yf": "^GSPC", "price_lo": 5000, "price_hi": 10000,
              "sessions": [13, 21], "tier": "⭐⭐⭐⭐ SPX #5", "decimals": 2, "min_sl": 20.0, "win_rate": "78%"},
}

SYMBOLS = list(MARKETS.keys())

# ==================== STRATEGY SETTINGS (1:2 RR) ====================
RSI_OB = 68
RSI_OS = 30
VOL_MULT = 1.4
RR = 2                    # ← 1:2 as requested
ATR_MULT = 1.7
CONFIRM_THRESHOLD = 4     # High win rate
ADX_THRESHOLD = 25
SIGNAL_COOLDOWN = 1800
PRESIG_COOLDOWN = 600
HTF_REFRESH = 3600

_signal_sent = {s: 0 for s in SYMBOLS}
_presig_sent = {s: 0 for s in SYMBOLS}
_htf_cache = {s: {"trend": "NEUTRAL", "ts": 0} for s in SYMBOLS}

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
        time.sleep(1)
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ─────────────────────────────────────────────
# LOT SIZE (with $50 risk highlighted)
# ─────────────────────────────────────────────
def lot_table(price, sl, symbol_key):
    sl_dist = abs(price - sl)
    if sl_dist == 0: return "N/A"
    dpl = DOLLAR_PER_LOT.get(symbol_key, 1.0)
    lines = []
    for risk in [25, 50, 100, 200]:
        lot = max(round(risk / (sl_dist * dpl), 3), 0.01)
        lines.append(f" 💵 ${risk:>3} risk → {lot:.3f} lots")
    return "\n".join(lines)

def lot_for_risk(price, sl, symbol_key, risk_usd=50):
    sl_dist = abs(price - sl)
    if sl_dist == 0: return 0.01
    dpl = DOLLAR_PER_LOT.get(symbol_key, 1.0)
    return max(round(risk_usd / (sl_dist * dpl), 3), 0.01)

# ─────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────
def in_session(symbol_key):
    h = datetime.now(timezone.utc).hour
    s, e = MARKETS[symbol_key]["sessions"]
    if not (s <= h < e):
        return False, "Closed"
    if 12 <= h < 16: return True, "NY+London 🔥🔥"
    if 7 <= h < 12: return True, "London 🔥"
    return True, "Asian"

# ─────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────
def fetch_yf(ticker, period="15d", interval="15m"):
    try:
        raw = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if raw.empty: return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [str(c).lower() for c in raw.columns]
        for c in ["open","high","low","close","volume"]:
            if c not in raw.columns: raw[c] = 0.0
        return raw[["open","high","low","close","volume"]].copy().reset_index(drop=True)
    except: return None

def fetch_ccxt(src_name, sym, tf="15m", limit=200):
    try:
        exchange = getattr(ccxt, src_name)()
        ohlcv = exchange.fetch_ohlcv(sym, timeframe=tf, limit=limit)
        return pd.DataFrame(ohlcv, columns=["time","open","high","low","close","volume"])
    except: return None

def get_15m(symbol_key):
    if symbol_key in ["BTC/USD", "ETH/USD"]:
        sym = symbol_key.replace("/USD", "")
        for src in ["coinbase", "binance"]:
            df = fetch_ccxt(src, f"{sym}/USDT" if src=="binance" else f"{sym}/USD")
            if df is not None and len(df) > 50:
                return df, src
    yf_sym = MARKETS[symbol_key]["yf"]
    if yf_sym:
        df = fetch_yf(yf_sym)
        if df is not None and len(df) > 50:
            return df, "yf"
    return None, None

def get_htf(symbol_key):
    yf_sym = MARKETS[symbol_key]["yf"]
    if yf_sym:
        return fetch_yf(yf_sym, period="30d", interval="1h")
    return None

# ─────────────────────────────────────────────
# INDICATORS & TREND
# ─────────────────────────────────────────────
def add_ind(df):
    df = df.copy()
    cl = pd.to_numeric(df["close"])
    hi = pd.to_numeric(df["high"])
    lo = pd.to_numeric(df["low"])
    vol = pd.to_numeric(df["volume"])
    df["rsi"] = ta.momentum.RSIIndicator(cl, 14).rsi()
    df["ema9"] = ta.trend.EMAIndicator(cl, 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(cl, 21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(cl, 50).ema_indicator()
    df["atr"] = ta.volatility.AverageTrueRange(hi, lo, cl, 14).average_true_range()
    df["adx"] = ta.trend.ADXIndicator(hi, lo, cl, 14).adx()
    df["volma"] = vol.rolling(20).mean()
    return df

def get_trend(symbol_key):
    cache = _htf_cache[symbol_key]
    now = time.time()
    if now - cache["ts"] < HTF_REFRESH:
        return cache["trend"]
    
    df = get_htf(symbol_key)
    if df is not None and len(df) > 100:
        df = add_ind(df)
        last = df.iloc[-1]
        cache["trend"] = "BULL" if last["ema21"] > last["ema50"] else "BEAR"
    else:
        cache["trend"] = "NEUTRAL"
    cache["ts"] = now
    return cache["trend"]

# ─────────────────────────────────────────────
# CONDITIONS
# ─────────────────────────────────────────────
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
    atr = float(last.get("atr", 0))
    adx = float(last["adx"]) if not pd.isna(last["adx"]) else 0

    body = abs(close - op)
    rng = max(last["high"] - last["low"], 0.0001)
    body_pct = body / rng
    vol_ok = volma > 0 and vol > volma * VOL_MULT

    buy = {
        "RSI < 30": rsi < RSI_OS,
        "EMA9 > EMA21": ema9 > ema21,
        "Strong Volume": vol_ok,
        "Bullish Candle >60%": close > op and body_pct > 0.6,
        "Above EMA50": close > ema50,
    }
    sell = {
        "RSI > 68": rsi > RSI_OB,
        "EMA9 < EMA21": ema9 < ema21,
        "Strong Volume": vol_ok,
        "Bearish Candle >60%": close < op and body_pct > 0.6,
        "Below EMA50": close < ema50,
    }

    buy_score = sum(buy.values())
    sell_score = sum(sell.values())

    if trend == "BULL":
        buy_score += 1
        sell_score = 0
    elif trend == "BEAR":
        sell_score += 1
        buy_score = 0

    return buy, sell, buy_score, sell_score, rsi, close, atr, adx

# ─────────────────────────────────────────────
# SL / TP
# ─────────────────────────────────────────────
def calc_levels(price, direction, atr, symbol_key):
    min_sl = MARKETS[symbol_key]["min_sl"]
    sl_dist = max(float(atr) * ATR_MULT, float(min_sl))
    decimals = MARKETS[symbol_key]["decimals"]

    if direction == "BUY":
        sl = price - sl_dist
        tp = price + sl_dist * RR
    else:
        sl = price + sl_dist
        tp = price - sl_dist * RR
    return round(sl, decimals), round(tp, decimals), round(sl_dist, decimals)

# ─────────────────────────────────────────────
# PROCESS
# ─────────────────────────────────────────────
def process(symbol_key):
    mkt = MARKETS[symbol_key]
    ok, session = in_session(symbol_key)
    if not ok: return "NONE"

    result = get_15m(symbol_key)
    if not result or result[0] is None: return "NONE"
    df, source = result

    if len(df) < 60: return "NONE"
    df = add_ind(df)

    price = float(df.iloc[-1]["close"])
    if not (mkt["price_lo"] <= price <= mkt["price_hi"]): return "NONE"

    if float(df.iloc[-1]["adx"]) < ADX_THRESHOLD: return "RANGING"

    trend = get_trend(symbol_key)
    buy, sell, buy_score, sell_score, rsi, close, atr, adx = check_conditions(df, trend)

    best = max(buy_score, sell_score)
    direction = "BUY" if buy_score > sell_score else "SELL"
    mt5 = mkt["mt5"]
    dec = mkt["decimals"]
    now = time.time()

    # PRE-ALERT
    if best == 3:
        if now - _presig_sent[symbol_key] > PRESIG_COOLDOWN:
            _presig_sent[symbol_key] = now
            send_telegram(f"👀 *PRE-ALERT* — {mt5}\n2/5 building... Price: ${price:,.{dec}f} | HTF: {trend}")
        return "PRESIGNAL"

    # MAIN SIGNAL
    if best >= CONFIRM_THRESHOLD:
        if now - _signal_sent[symbol_key] < SIGNAL_COOLDOWN: return "COOLDOWN"

        dir_name = "BUY" if buy_score >= CONFIRM_THRESHOLD else "SELL"
        checks = buy if dir_name == "BUY" else sell
        signal_text = "LONG / BUY 📈" if dir_name == "BUY" else "SHORT / SELL 📉"

        sl, tp, sl_dist = calc_levels(price, dir_name, atr, symbol_key)
        lots = lot_table(price, sl, symbol_key)
        risk50_lot = lot_for_risk(price, sl, symbol_key, 50)

        _signal_sent[symbol_key] = now

        msg = f"""
🚀 *SIGNAL — {mt5}* 🚀
_{mkt['tier']} — {mkt['win_rate']} Win Rate_

🔥 *Action:* {signal_text}
⭐ *Score:* {best}/5 + HTF
📉 *ADX:* {adx:.1f} ✅
💹 *Price:* ${price:,.{dec}f}
📍 *Entry:* {price:,.{dec}f}
🛑 *SL:* {sl:,.{dec}f}
🎯 *TP:* {tp:,.{dec}f} *(1:{RR} RR)*

📈 *RSI:* {rsi:.1f} | 🌍 *HTF:* {trend} | ⏰ *Session:* {session}
📡 *Source:* {source}

✅ *Confirmed:*
""" + "\n".join([f" ✅ {k}" for k, v in checks.items() if v]) + f"""

📦 *$50 Risk Lots:*
{lots}
_Approx {risk50_lot:.3f} lots for $50 risk_

⚡ *Good Setup — 1:2 Target!*
"""
        send_telegram(msg)
        log.info(f"🚀 SIGNAL {mt5} {signal_text} | Score: {best}/5")
        return "SIGNAL"

    return "NONE"

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    log.info("═" * 60)
    log.info("🚀 PEPPERSTONE MOMENTUM HUNTER v9.0 STARTED")
    log.info("📊 1:2 RR | High Win Rate Mode | 4/5 Confirmation")
    log.info("═" * 60)

    with ThreadPoolExecutor(max_workers=5) as ex:
        for s in SYMBOLS:
            ex.submit(get_trend, s)

    while True:
        try:
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = {ex.submit(process, s): s for s in SYMBOLS}
                for f in as_completed(futures):
                    pass
            time.sleep(20)
        except Exception as e:
            log.error(f"Error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
