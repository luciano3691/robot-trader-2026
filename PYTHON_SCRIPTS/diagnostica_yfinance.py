"""
DIAGNOSTICA YFINANCE - Robot Trader 2026
=========================================
Esegui questo script sul tuo PC per mappare tutti i campi disponibili.
Copia l'OUTPUT e incollalo nella chat con Claude.

Uso: python diagnostica_yfinance.py
"""
import yfinance as yf
import json
import sys

# Ticker di test: 1 azione, 1 ETF USA, 1 ETF EU, 1 fondo
TEST_TICKERS = {
    'AZIONE': 'AAPL',
    'ETF_USA': 'SPY',
    'ETF_EU': 'VWCE.DE',
    'FONDO': 'VVIPX',
}

def safe_str(v):
    if v is None:
        return 'None'
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)[:200]
    return str(v)[:200]

print("=" * 70)
print("DIAGNOSTICA YFINANCE - Robot Trader 2026")
print(f"yfinance version: {yf.__version__}")
print(f"Python version: {sys.version}")
print("=" * 70)

for tipo, ticker_sym in TEST_TICKERS.items():
    print(f"\n{'=' * 70}")
    print(f"TIPO: {tipo} | TICKER: {ticker_sym}")
    print("=" * 70)
    
    try:
        t = yf.Ticker(ticker_sym)
        
        # === INFO DICT ===
        print(f"\n--- ticker.info (tutte le chiavi) ---")
        info = t.info
        if info:
            # Stampa TUTTE le chiavi ordinate
            for k in sorted(info.keys()):
                print(f"  {k}: {safe_str(info[k])}")
            
            # Campi critici che ci servono
            print(f"\n--- CAMPI CRITICI ---")
            campi_critici = [
                'enterpriseToFreeCashflow', 'enterpriseValue', 'freeCashflow',
                'totalAssets', 'netAssets', 'volume', 'averageVolume',
                'expenseRatio', 'annualReportExpenseRatio', 'fundFamily',
                'quoteType', 'sector', 'industry',
                'trailingPE', 'forwardPE', 'priceToBook', 'returnOnEquity',
                'debtToEquity', 'operatingCashflow', 'marketCap',
                'numberOfAnalystOpinions', 'category',
            ]
            for campo in campi_critici:
                val = info.get(campo, '<<MANCANTE>>')
                print(f"  {campo}: {safe_str(val)}")
        else:
            print("  INFO VUOTO!")
        
        # === FAST_INFO ===
        print(f"\n--- ticker.fast_info ---")
        try:
            fi = t.fast_info
            if fi:
                for attr in dir(fi):
                    if not attr.startswith('_'):
                        try:
                            print(f"  {attr}: {safe_str(getattr(fi, attr))}")
                        except:
                            print(f"  {attr}: <<ERRORE>>")
        except Exception as e:
            print(f"  fast_info ERRORE: {e}")
        
        # === FUNDS_DATA (solo per ETF e fondi) ===
        if tipo != 'AZIONE':
            print(f"\n--- ticker.funds_data ---")
            try:
                fd = t.funds_data
                if fd:
                    print(f"  fund_overview: {safe_str(fd.fund_overview)}")
                    print(f"  fund_operations:\n{fd.fund_operations}")
                    print(f"  description: {safe_str(fd.description)[:100]}")
                else:
                    print("  funds_data VUOTO!")
            except Exception as e:
                print(f"  funds_data ERRORE: {e}")
        
        # === CASHFLOW (per calcolo FCF azioni) ===
        if tipo == 'AZIONE':
            print(f"\n--- ticker.cashflow (ultime colonne) ---")
            try:
                cf = t.cashflow
                if cf is not None and not cf.empty:
                    print(f"  Righe disponibili: {list(cf.index)}")
                    # Cerca Free Cash Flow
                    for row_name in cf.index:
                        if 'free' in row_name.lower() or 'fcf' in row_name.lower() or 'capital' in row_name.lower():
                            print(f"  >>> {row_name}: {cf.loc[row_name].iloc[0]}")
                else:
                    print("  cashflow VUOTO!")
            except Exception as e:
                print(f"  cashflow ERRORE: {e}")
        
    except Exception as e:
        print(f"  ERRORE GENERALE: {e}")

print(f"\n{'=' * 70}")
print("FINE DIAGNOSTICA - Copia tutto l'output e incollalo nella chat")
print("=" * 70)
