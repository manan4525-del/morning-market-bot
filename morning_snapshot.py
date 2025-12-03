# morning_snapshot.py
# Fetch simple market snapshot and send to Telegram
# Works on GitHub Actions (no server needed)

import os
import datetime
import yfinance as yf
import requests

# Read secrets from environment (set these in GitHub repo secrets)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Tickers we will try (Yahoo Finance symbols)
TICKERS = {
    "US 10Y (approx)": "^TNX",    # US 10Y yield (Yahoo, may represent yield*1)
    "Brent (USD/bbl)": "BZ=F",
    "DXY (Dollar Index)": "DX-Y.NYB",  # fallback to ^DXY if needed
    "USD/INR": "USDINR=X",
    "S&P 500": "^GSPC"
}

def safe_fetch(ticker):
    """Return last available price for ticker or None."""
    try:
        t = yf.Ticker(ticker)
        # try intraday last value (1 minute), fallback to regularMarketPrice
        df = t.history(period="1d", interval="1m")
        if df is not None and not df.empty:
            return float(df['Close'].iloc[-1])
        info = t.info if hasattr(t, 'info') else {}
        val = info.get('regularMarketPrice') or info.get('previousClose')
        return float(val) if val is not None else None
    except Exception as e:
        print("fetch error", ticker, e)
        return None

def make_message():
    # Build timestamp in IST
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    ts = now.strftime("%Y-%m-%d %H:%M IST")
    lines = [f"📊 Morning Market Snapshot — {ts}", ""]
    results = {}
    for name, ticker in TICKERS.items():
        val = safe_fetch(ticker)
        # small fallback: if DXY ticker fails, try ^DXY; if USDINR fails, try INR=X alternatives later
        if val is None and ticker == "DX-Y.NYB":
            val = safe_fetch("^DXY")
        if val is None and ticker == "USDINR=X":
            # some regions may not support USDINR=X; attempt "INR=X" fallback isn't correct; leave as N/A
            val = None
        results[name] = val
        lines.append(f"{name}: {val if val is not None else 'N/A'}  (ticker: {ticker})")

    # Quick read heuristics (very simple)
    quick = []
    us10 = results.get("US 10Y (approx)")
    if us10 is not None:
        try:
            if us10 > 4.6:
                quick.append("US10Y high → risk-off")
            elif us10 < 4.2:
                quick.append("US10Y low → risk-on possible")
        except:
            pass
    dxyv = results.get("DXY (Dollar Index)")
    if dxyv is not None and dxyv > 105:
        quick.append("DXY strong → INR pressure possible")
    brentv = results.get("Brent (USD/bbl)")
    if brentv is not None and brentv > 95:
        quick.append("Brent high → inflation pressure")

    lines.append("")
    lines.append("⚡ Quick read: " + (" | ".join(quick) if quick else "No major global red flags detected"))

    return "\n".join(lines)

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing Telegram BOT_TOKEN or CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=15)
        print("telegram status", r.status_code, r.text)
        return r.status_code == 200
    except Exception as e:
        print("telegram send error", e)
        return False

if __name__ == "__main__":
    msg = make_message()
    print(msg)
    ok = send_telegram(msg)
    if ok:
        print("Message sent")
    else:
        print("Failed to send message")
