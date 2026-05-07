import time
import logging
import requests
import os
import pandas as pd
import ta
import yfinance as yf

# ═══════════════════════════════════════════════════════════════
# PEPPERSTONE INSTITUTIONAL FRAMEWORK v14.0 — Adaptive Engine
# Stable Railway Version (error handling + rate control)
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("v14.0")

# Telegram credentials
TOKEN   = os.getenv("TOKEN",   "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

# Market definitions
MARKETS = {
    "XAUUSD": {"yf":"GC=F","min_sl":25.0,"sessions":[7,20],"decimals":2},
    "BTCUSD": {"yf":"BTC-USD","min_sl":500.0,"sessions":[0,23],"decimals":2},
    "GBPUSD": {"yf":"GBPUSD=X","min_sl":0.0030,"sessions":[7,20],"decimals":5},
    "ETHUSD": {"yf":"ETH-USD","min_sl":25.0,"sessions":[0,23],"decimals":2},
    "US500":  {"yf":"^GSPC","min_sl":20.0,"sessions":[13,21],"decimals":2},
}

# Telegram sender with rate control
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
            log.warning(f"Telegram failed: {r.status_code}")
        time.sleep(1)  # rate control
    except Exception as e:
        log.error(f"Telegram error: {e}")

# Fetch data safely
def fetch_yf(ticker, period="15d", interval="15m"):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty: 
            log.warning(f"No data for {ticker}")
            return None
        df.columns = [c.lower() for c in df.columns]
        return df[["open","high","low","close","volume"]].reset_index(drop=True)
    except Exception as e:
        log.error(f"Data fetch error {ticker}: {e}")
        return None

# Indicators
def add_ind(df):
    try:
        cl = pd.to_numeric(df["close"])
        hi = pd.to_numeric(df["high"])
        lo = pd.to_numeric(df["low"])
        df["rsi"]   = ta.momentum.RSIIndicator(cl,14).rsi()
        df["ema9"]  = ta.trend.EMAIndicator(cl,9).ema_indicator()
        df["ema21"] = ta.trend.EMAIndicator(cl,21).ema_indicator()
        df["ema50"] = ta.trend.EMAIndicator(cl,50).ema_indicator()
        df["atr"]   = ta.volatility.AverageTrueRange(hi,lo,cl,14).average_true_range()
        df["adx"]   = ta.trend.ADXIndicator(hi,lo,cl,14).adx()
        return df
    except Exception as e:
        log.error(f"Indicator error: {e}")
        return df

# Institutional filters
def detect_liquidity_sweep(df): 
    return df["low"].iloc[-1]<df["low"].iloc[-5:].min() or df["high"].iloc[-1]>df["high"].iloc[-5:].max()

def detect_order_block(df): 
    return abs(df["close"].iloc[-1]-df["open"].iloc[-1])<df["atr"].iloc[-1]

def detect_fvg(df): 
    return abs(df["close"].iloc[-1]-df["open"].iloc[-1])>df["atr"].iloc[-1]

def detect_big_bar(df): 
    return (df["high"].iloc[-1]-df["low"].iloc[-1])>df["atr"].iloc[-1]*1.5

# Strategy check
def check_conditions(df, htf_bias):
    try:
        rsi   = df["rsi"].iloc[-1]
        ema9  = df["ema9"].iloc[-1]
        ema21 = df["ema21"].iloc[-1]
        ema50 = df["ema50"].iloc[-1]
        adx   = df["adx"].iloc[-1]
        price = df["close"].iloc[-1]

        conds = []
        if rsi>65: conds.append("RSI overbought")
        if rsi<35: conds.append("RSI oversold")
        if ema9>ema21: conds.append("EMA9 above EMA21")
        if ema9<ema21: conds.append("EMA9 below EMA21")
        if price>ema50: conds.append("Price above EMA50")
        if price<ema50: conds.append("Price below EMA50")
        if adx>22: conds.append("ADX trending")
        if detect_liquidity_sweep(df): conds.append("Liquidity sweep")
        if detect_order_block(df): conds.append("Order block")
        if detect_fvg(df): conds.append("FVG")
        if detect_big_bar(df): conds.append("Big-bar momentum")

        score = len(conds)
        return conds, score, htf_bias
    except Exception as e:
        log.error(f"Condition check error: {e}")
        return [],0,htf_bias

# Levels calc (structural SL + fixed 1:3 R:R)
def calc_levels(price, atr, direction, min_sl, df):
    try:
        if direction=="BUY":
            sl = min(df["low"].iloc[-5:]) - 0.5*atr
            tp = price + (price-sl)*3
        else:
            sl = max(df["high"].iloc[-5:]) + 0.5*atr
            tp = price - (sl-price)*3
        sl_dist = abs(price-sl)
        if sl_dist<min_sl: sl_dist=min_sl
        return sl, tp, sl_dist
    except Exception as e:
        log.error(f"Level calc error: {e}")
        return price, price, 0

# Breakeven alert
def breakeven_alert(sym, entry, sl, tp, price, decimals):
    msg = f"""
⚠️ Breakeven Trigger — {sym}
──────────────────────────────
Trade tightened to breakeven.
📍 Entry: {entry:.{decimals}f}
🛑 SL moved to: {sl:.{decimals}f} (breakeven)
🎯 TP remains: {tp:.{decimals}f} (1:3 target)
"""
    send_telegram(msg)

# Main loop
def run_bot():
    for sym, info in MARKETS.items():
        df = fetch_yf(info["yf"])
        if df is None or len(df)<50: continue
        df = add_ind(df)
        htf_bias = "BULL" if df["ema50"].iloc[-1]>df["ema21"].iloc[-1] else "BEAR"
        conds, score, bias = check_conditions(df, htf_bias)
        price = df["close"].iloc[-1]
        atr   = df["atr"].iloc[-1]
        direction = "BUY" if "RSI oversold" in conds or "EMA9 above EMA21" in conds else "SELL"
        sl,tp,sl_dist = calc_levels(price, atr, direction, info["min_sl"], df)

        if score>=3:
            msg = f"""
🚀 *SIGNAL — {sym}* 🚀
🔥 *Action:* {direction}
⭐ *Score:* {score}/10 + HTF {bias}
💹 *Price:* {price:.{info['decimals']}f}
🛑 *Stop Loss:* {sl:.{info['decimals']}f}
🎯 *Take Profit:* {tp:.{info['decimals']}f}
⚖️ *R:R:* 1:3
"""
            send_telegram(msg)

            # Breakeven check
            if direction=="BUY" and price>=sl+sl_dist:
                breakeven_alert(sym, price, price, tp, price, info["decimals"])
            elif direction=="SELL" and price<=sl-sl_dist:
                breakeven_alert(sym, price, price, tp, price, info["decimals"])

if __name__=="__main__":
    run_bot()
