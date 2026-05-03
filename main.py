import time
import logging
import requests
import ccxt
import pandas as pd
import ta  # technical analysis library

# 1. LOGGING SETUP
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("Binance_Combined_Scanner")

# 2. CONFIGURATION
TOKEN   = "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk"
CHAT_ID = "8783763018"
SYMBOLS = ["BTC/USDT", "XAUUSDT"]   # BTC spot + Gold perpetual
TIMEFRAME_15M = "15m"
TIMEFRAME_1M  = "1m"
CANDLE_LIMIT  = 200

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

# 4. BINANCE DATA FETCH
def get_binance_data(symbol):
    try:
        exchange = ccxt.binance()
        
        # Fetch 15m candles
        ohlcv_15m = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME_15M, limit=CANDLE_LIMIT)
        df_15m = pd.DataFrame(ohlcv_15m, columns=["time","open","high","low","close","volume"])
        
        # Fetch 1m candles
        ohlcv_1m = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME_1M, limit=CANDLE_LIMIT)
        df_1m = pd.DataFrame(ohlcv_1m, columns=["time","open","high","low","close","volume"])
        
        # Indicators
        df_15m["EMA50"] = ta.trend.EMAIndicator(df_15m["close"], window=50).ema_indicator()
        df_15m["EMA200"] = ta.trend.EMAIndicator(df_15m["close"], window=200).ema_indicator()
        
        df_1m["RSI"] = ta.momentum.RSIIndicator(df_1m["close"], window=14).rsi()
        
        price = df_1m["close"].iloc[-1]
        rsi = df_1m["RSI"].iloc[-1]
        ema50_15m = df_15m["EMA50"].iloc[-1]
        ema200_15m = df_15m["EMA200"].iloc[-1]
        
        return price, rsi, ema50_15m, ema200_15m
    
    except Exception as e:
        log.error(f"⚠️ Binance Fetch Error for {symbol}: {e}")
        return None

# 5. SCANNER LOGIC
def scan_symbol(symbol):
    data = get_binance_data(symbol)
    if data is None:
        return
    
    price, rsi, ema50, ema200 = data
    is_bullish = ema50 > ema200
    
    signal = None
    sl = None
    tp_primary = None

    # Strategy: RSI Pullback in a 15m Trend
    if is_bullish and rsi < RSI_OVERSOLD:
        signal = "LONG / BUY"
        sl = price * (1 - STOP_PCT)
        tp_primary = price + (price - sl) * RR_RATIO
    elif not is_bullish and rsi > RSI_OVERBOUGHT:
        signal = "SHORT / SELL"
        sl = price * (1 + STOP_PCT)
        tp_primary = price - (sl - price) * RR_RATIO

    if signal:
        header = "🚨 BINANCE BTC SIGNAL 🚨" if symbol == "BTC/USDT" else "🚨 BINANCE GOLD SIGNAL 🚨"
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
    log.info("🚀 STARTING COMBINED SCANNER: BTC + GOLD (1:2 TP only)")
    while True:
        try:
            for symbol in SYMBOLS:
                scan_symbol(symbol)
            time.sleep(30)  # safe scan interval between cycles
        except Exception as e:
            log.error(f"Scanner Loop Error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
