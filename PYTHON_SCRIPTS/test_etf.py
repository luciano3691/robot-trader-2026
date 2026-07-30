import yfinance as yf

etf = "VWCE.DE"
ticker = yf.Ticker(etf)
info = ticker.info

print(f"=== CAMPI DISPONIBILI PER {etf} ===\n")
for key in sorted(info.keys()):
    value = info[key]
    if value is not None and value != '':
        print(f"{key}: {value}")
