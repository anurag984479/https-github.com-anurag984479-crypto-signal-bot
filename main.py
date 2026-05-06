import time
import logging
import requests
import pandas as pd
import ta
import yfinance as yf
import sys

# ═══════════════════════════════════════════════════════════════
# PEPPERSTONE ZONE SNIPER v2.0 — ULTIMATE FAST SCAN + HEARTBEAT
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("ZoneSniper")

TOKEN = "8641713322:AAHZeJOz0_LILD076P1ShvXSfCqQ1xrpFlk"
CHAT_ID = "8783763018"

MARKETS = {
    "XAU/USD": {"mt5": "XAUUSD.Qraw", "yf": "GC=F", "dec": 2},
    "BTC/USD": {"mt5": "BTC-USD", "yf": "BTC-USD", "dec": 2},
    "ETH/USD": {"mt5": "ETH-USD", "yf": "ETH-USD", "dec": 2},
    "GBP/USD": {"mt5": "GBPUSD.Qraw", "yf": "GBPUSD=X", "dec": 5},
    "EUR/USD": {"mt5": "EURUSD.Qraw", "yf": "EURUSD=X", "dec": 5},
    "US500":   {"mt5": "US500.Qraw",  "yf": "^GSPC", "dec": 2},
    "USTEC":   {"mt5": "USTEC.Qraw",  "yf": "^NDX", "dec": 2},
}

def get_data(ticker, tf="5m"):
    try:
        df = yf.download(ticker, period="30d" if tf == "1h" else "7d", interval=tf, progress=False)
        if df is None or df.empty or len(df) < 201:[cite: 2]
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]
        
        # Sniper Indicators[cite: 1]
        df["ema_fast"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
        df["ema_slow"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        df["vol_ma"] = df["volume"].rolling(20).mean()
        return df.dropna()
    except:
        return None

def monitor():
    log.info("🎯 ZONE SNIPER v2.0: HIGH-SPEED PULSE ACTIVE")
    cycle_count = 0
    
    while True:
        cycle_count += 1
        # Heartbeat Pulse
        sys.stdout.write(f"\r💓 Heartbeat: Cycle {cycle_count} | Scanning Pepperstone Feed...")
        sys.stdout.flush()

        for name, info in MARKETS.items():
            df_5m = get_data(info['yf'], "5m")
            df_1h = get_data(info['yf'], "1h")

            if df_5m is None or df_1h is None:
                continue

            # Sniper Execution Logic[cite: 1]
            last_5m = df_5m.iloc[-1]
            last_1h = df_1h.iloc[-1]
            
            htf_bull = last_1h['ema_fast'] > last_1h['ema_slow']
            ltf_bull = last_5m['ema_fast'] > last_5m['ema_slow']
            vol_spike = last_5m['volume'] > (last_5m['vol_ma'] * 1.3)

            if ltf_bull and htf_bull and last_5m['rsi'] < 35 and vol_spike:
                send_signal(name, "BUY", last_5m['close'], info['dec'])
                print(f"\n🚀 [SIGNAL] {name} BUY @ {last_5m['close']}")[cite: 2]
            elif not ltf_bull and not htf_bull and last_5m['rsi'] > 65 and vol_spike:
                send_signal(name, "SELL", last_5m['close'], info['dec'])
                print(f"\n🚀 [SIGNAL] {name} SELL @ {last_5m['close']}")[cite: 2]
            
            time.sleep(0.2) # Ultra-fast interval
            
def send_signal(asset, side, price, dec):
    msg = f"🎯 *ZONE SNIPER — {MARKETS[asset]['mt5']}*\n🔥 *Action:* {side}\n💹 *Entry:* {price:.{dec}f}"
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except:
        pass

if __name__ == "__main__":
    monitor()