import time
import logging
import requests
import ccxt
import pandas as pd
import ta
import yfinance as yf
import os

# 1. LOGGING SETUP
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("Combined_Scanner")

# 2. CONFIGURATION
TOKEN   = os.getenv("TOKEN", "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk")
CHAT_ID = os.getenv("CHAT_ID", "8783763018")

SYMBOLS = ["BTC/USD", "GC=F"]   # BTC via Coinbase, Gold via Yahoo Finance
TIMEFRAME = "15m"
CANDLE_LIMIT = 200

# Strategy thresholds
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
STOP_PCT = 0.005        # 0.5% stop distance
RR_RATIO = 2            # fixed 1:2 target

# 3. NOTIFIER
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
        log.info("✅ Signal sent to Telegram.")
    except Exception as e:
        log.error(f"❌ Telegram delivery failed: {e}")

# 4. DATA FETCH
def get_btc_data():
    try:
        exchange = ccxt.coinbase()
        ohlcv = exchange.fetch_ohlcv("BTC/USD", timeframe=TIMEFRAME, limit=CANDLE_LIMIT)
        df = pd.DataFrame(ohlcv, columns=["time","open","high","low","close","volume"])
        df["EMA50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
        df["EMA200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
        df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        price = df["close"].iloc[-1]
        rsi = df["RSI"].iloc[-1]
        ema50 = df["EMA50"].iloc[-1]
        ema200 = df["EMA200"].iloc[-1]
        return price, rsi, ema50, ema200
    except Exception as e:
        log.error(f"⚠️ Coinbase Fetch Error for BTC/USD: {e}")
        return None

def get_gold_data():
    try:
        # Use 5m interval instead of 1m to avoid Yahoo errors
        df = yf.download("GC=F", interval="5m", period="5d")
        df["EMA50"] = ta.trend.EMAIndicator(df["Close"], window=50).ema_indicator()
        df["EMA200"] = ta.trend.EMAIndicator(df["Close"], window=200).ema_indicator()
        df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
        price = df["Close"].iloc[-1]
        rsi = df["RSI"].iloc[-1]
        ema50 = df["EMA50"].iloc[-1]
        ema200 = df["EMA200"].iloc[-1]
        return price, rsi, ema50, ema200
    except Exception as e:
        log.error(f"⚠️ Yahoo Finance Fetch Error for Gold: {e}")
        return None

# 5. SCANNER LOGIC
def scan_symbol(symbol):
    if symbol == "BTC/USD":
        data = get_btc_data()
    else:
        data = get_gold_data()

    if data is None:
        return
    
    price, rsi, ema50, ema200 = data
    is_bullish = ema50 > ema200
    
    signal = None
    sl = None
    tp_primary = None

    if is_bullish and rsi < RSI_OVERSOLD:
        signal = "LONG / BUY"
        sl = price * (1 - STOP_PCT)
        tp_primary = price + (price - sl) * RR_RATIO
    elif not is_bullish and rsi > RSI_OVERBOUGHT:
        signal = "SHORT / SELL"
        sl = price * (1 + STOP_PCT)
        tp_primary = price - (sl - price) * RR_RATIO

    if signal:
        header = "🚨 COINBASE BTC SIGNAL 🚨" if symbol == "BTC/USD" else "🚨 GOLD SIGNAL 🚨"
        msg = (
            f"{header}\n\n"
            f"🔥 *Action:* {signal}\n"
            f"💹 *Current Price:* ${price:,.2f}\n\n"
            f"📍 *Entry:* {price:,.2f}\n"
            f"🛑 *Stop Loss:* {sl:,.2f}\n"
            f"🎯 Take Profit: {tp_primary:,.2f}\n"
            f"⚖️ Risk-Reward: 1:2.00\n\n"
            f"📊 *Trend (15m):* {'Bullish 📈' if is_bullish else 'Bearish 📉'}\n"
            f"🔗 Open Chart"
        )
        send_telegram_alert(msg)
        log.info(f"Signal Found for {symbol}: {signal}. Entering 10-minute cooldown.")
        time.sleep(600)
    else:
        log.info(f"Heartbeat — {symbol} Price: {price:.2f}, RSI: {rsi:.2f}, Trend: {'Bullish' if is_bullish else 'Bearish'}")

# 6. MAIN LOOP
def main():
    log.info("🚀 STARTING COMBINED SCANNER: BTC (Coinbase) + GOLD (Yahoo Finance GC=F, 5m)")
    while True:
        try:
            for symbol in SYMBOLS:
                scan_symbol(symbol)
            time.sleep(30)
        except Exception as e:
            log.error(f"Scanner Loop Error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
