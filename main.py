import time
import logging
import requests
import ccxt
import pandas as pd
import ta
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

SYMBOLS = ["BTC/USD", "XAU/USD"]
TIMEFRAME = "15m"
CANDLE_LIMIT = 200

RSI_OVERSOLD  = 35
RSI_OVERBOUGHT = 65
STOP_PCT = 0.005
RR_RATIO = 2

# TradingView chart links (best free option, no auth needed)
CHART_LINKS = {
    "BTC/USD": "https://www.tradingview.com/chart/?symbol=COINBASE%3ABTCUSD&interval=15",
    "XAU/USD": "https://www.tradingview.com/chart/?symbol=TVC%3AGOLD&interval=15",
}

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

def fetch_ohlcv_df(exchange_obj, symbol, timeframe, limit):
    """Generic OHLCV fetcher with indicators."""
    ohlcv = exchange_obj.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["time","open","high","low","close","volume"])
    df["close"] = pd.to_numeric(df["close"])
    df["EMA50"]  = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    df["EMA200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
    df["RSI"]    = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    return df

def get_btc_data():
    try:
        exchange = ccxt.coinbase()
        df = fetch_ohlcv_df(exchange, "BTC/USD", TIMEFRAME, CANDLE_LIMIT)
        row = df.iloc[-1]
        return row["close"], row["RSI"], row["EMA50"], row["EMA200"]
    except Exception as e:
        log.error(f"⚠️ Coinbase Fetch Error for BTC/USD: {e}")
        return None

def get_gold_data():
    """
    Kraken uses 'XAU/USD' — but it's often unavailable on spot.
    Fallback chain: Kraken → Bitfinex (XAUUSD) → yfinance (XAUUSD=X)
    """
    # --- Try Kraken with correct symbol ---
    for kraken_sym in ["XAU/USD", "XAUUSD"]:
        try:
            exchange = ccxt.kraken()
            df = fetch_ohlcv_df(exchange, kraken_sym, TIMEFRAME, CANDLE_LIMIT)
            row = df.iloc[-1]
            log.info(f"Gold data fetched from Kraken ({kraken_sym})")
            return row["close"], row["RSI"], row["EMA50"], row["EMA200"]
        except Exception as e:
            log.warning(f"Kraken {kraken_sym} failed: {e}")

    # --- Fallback: Bitfinex ---
    try:
        exchange = ccxt.bitfinex()
        df = fetch_ohlcv_df(exchange, "XAU/USD", TIMEFRAME, CANDLE_LIMIT)
        row = df.iloc[-1]
        log.info("Gold data fetched from Bitfinex")
        return row["close"], row["RSI"], row["EMA50"], row["EMA200"]
    except Exception as e:
        log.warning(f"Bitfinex Gold failed: {e}")

    # --- Final fallback: yfinance ---
    try:
        import yfinance as yf
        raw = yf.download("GC=F", period="5d", interval="15m", progress=False)
        if raw.empty:
            raise ValueError("Empty yfinance response")
        # yfinance MultiIndex fix — flatten columns
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        df = raw[["Open","High","Low","Close","Volume"]].copy()
        df.columns = ["open","high","low","close","volume"]
        df["close"] = pd.to_numeric(df["close"])
        df["EMA50"]  = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
        df["EMA200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
        df["RSI"]    = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        row = df.iloc[-1]
        log.info("Gold data fetched from yfinance (GC=F futures)")
        return row["close"], row["RSI"], row["EMA50"], row["EMA200"]
    except Exception as e:
        log.error(f"⚠️ All Gold data sources failed. Last error: {e}")
        return None

# 5. SCANNER LOGIC
def scan_symbol(symbol):
    data = get_btc_data() if symbol == "BTC/USD" else get_gold_data()
    if data is None:
        return

    price, rsi, ema50, ema200 = data
    is_bullish = ema50 > ema200
    chart_url  = CHART_LINKS.get(symbol, "https://www.tradingview.com")

    signal      = None
    sl          = None
    tp_primary  = None

    if is_bullish and rsi < RSI_OVERSOLD:
        signal     = "LONG / BUY"
        sl         = price * (1 - STOP_PCT)
        tp_primary = price + (price - sl) * RR_RATIO
    elif not is_bullish and rsi > RSI_OVERBOUGHT:
        signal     = "SHORT / SELL"
        sl         = price * (1 + STOP_PCT)
        tp_primary = price - (sl - price) * RR_RATIO

    if signal:
        header = "🚨 COINBASE BTC SIGNAL 🚨" if symbol == "BTC/USD" else "🚨 GOLD SIGNAL 🚨"
        msg = (
            f"{header}\n\n"
            f"🔥 *Action:* {signal}\n"
            f"💹 *Current Price:* ${price:,.2f}\n\n"
            f"📍 *Entry:* {price:,.2f}\n"
            f"🛑 *Stop Loss:* {sl:,.2f}\n"
            f"🎯 *Take Profit:* {tp_primary:,.2f}\n"
            f"⚖️ *Risk-Reward:* 1:2.00\n\n"
            f"📊 *Trend (15m):* {'Bullish 📈' if is_bullish else 'Bearish 📉'}\n"
            f"📈 *RSI:* {rsi:.1f}\n\n"
            f"🔗 [Open TradingView Chart]({chart_url})"
        )
        send_telegram_alert(msg)
        log.info(f"Signal Found for {symbol}: {signal}. Entering 10-minute cooldown.")
        time.sleep(600)
    else:
        log.info(
            f"Heartbeat — {symbol} | Price: {price:.2f} | "
            f"RSI: {rsi:.2f} | Trend: {'Bullish' if is_bullish else 'Bearish'}"
        )

# 6. MAIN LOOP
def main():
    log.info("🚀 STARTING COMBINED SCANNER: BTC (Coinbase) + GOLD (Kraken→Bitfinex→yfinance, 15m)")
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