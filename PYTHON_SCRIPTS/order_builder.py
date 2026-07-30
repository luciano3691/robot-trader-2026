# -*- coding: utf-8 -*-
"""
ORDER BUILDER - Fuerte Screener
Genera e invia email di istruzioni d'acquisto al partner bancario.
"""

import os, io, csv, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    import yfinance as yf
    _YF_OK = True
except ImportError:
    _YF_OK = False

BREVO_SMTP_HOST     = os.getenv('BREVO_SMTP_HOST',     'smtp.gmail.com')
BREVO_SMTP_PORT     = 587
BREVO_SMTP_LOGIN    = os.getenv('BREVO_SMTP_LOGIN',    '')
BREVO_SMTP_PASSWORD = os.getenv('BREVO_SMTP_PASSWORD', '')


# ─── IBKR TICKER MAPPING ────────────────────────────────────────────────────

_IBKR_SUFFIX = {
    '.L':   ('SMART',    'GBP'),
    '.DE':  ('SMART',    'EUR'),
    '.PA':  ('SMART',    'EUR'),
    '.MI':  ('SMART',    'EUR'),
    '.MC':  ('SMART',    'EUR'),
    '.AS':  ('SMART',    'EUR'),
    '.SW':  ('SMART',    'CHF'),
    '.VX':  ('SMART',    'CHF'),
    '.ST':  ('SMART',    'SEK'),
    '.OL':  ('SMART',    'NOK'),
    '.CO':  ('SMART',    'DKK'),
    '.HE':  ('SMART',    'EUR'),
    '.BR':  ('SMART',    'EUR'),
    '.VI':  ('SMART',    'EUR'),
    '.LS':  ('SMART',    'EUR'),
    '.T':   ('TSE',      'JPY'),
    '.HK':  ('SEHK',     'HKD'),
    '.AX':  ('ASX',      'AUD'),
    '.TO':  ('TSX',      'CAD'),
    '.KS':  ('KSE',      'KRW'),
    '.SA':  ('BOVESPA',  'BRL'),
    '.NS':  ('NSE',      'INR'),
    '.TW':  ('TSEC',     'TWD'),
}


def _ticker_to_ibkr(ticker: str) -> tuple:
    """Converte ticker YF in (ibkr_symbol, exchange, currency)."""
    t = ticker.upper()
    for suffix, (exchange, currency) in _IBKR_SUFFIX.items():
        if t.endswith(suffix.upper()):
            return t[:-len(suffix)], exchange, currency
    return t, 'SMART', 'USD'


# ─── CSV GENERATORS ──────────────────────────────────────────────────────────

def genera_csv_ibkr(righe: list, riferimento: str = '', exec_params: dict = None) -> str:
    """
    CSV nel formato IBKR TWS Basket Trader.
    Import in TWS: File → Import Orders → seleziona file .csv → verifica → Trasmetti.
    """
    ep = exec_params or {}
    order_type = ep.get('tipo_ordine', 'MKT')          # MKT o LMT
    lmt_price  = ep.get('prezzo_limite', '')
    tif        = ep.get('validita', 'DAY')
    if tif not in ('DAY', 'GTC'):
        tif = 'DAY'

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Symbol', 'Action', 'Quantity', 'SecType', 'Exchange',
                'Currency', 'OrderType', 'LmtPrice', 'AuxPrice', 'TIF', 'OrderRef'])
    for r in righe:
        symbol, exchange, currency = _ticker_to_ibkr(r.get('ticker', ''))
        qty = int(r.get('quantita', 0))
        if qty <= 0:
            continue
        lmt = lmt_price if order_type == 'LMT' else ''
        w.writerow([symbol, 'BUY', qty, 'STK', exchange,
                    currency, order_type, lmt, '', tif, riferimento])
    return buf.getvalue()


def genera_csv_generico(righe: list, exec_params: dict = None) -> str:
    """
    CSV generico per inserimento manuale su qualsiasi piattaforma.
    """
    ep = exec_params or {}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Ticker_YF', 'Denominazione', 'Mercato', 'Valuta',
                'Prezzo_Rif', 'Quantita', 'Controvalore',
                'Tipo_Ordine', 'Prezzo_Limite', 'Stop_Loss', 'Take_Profit', 'Trailing_Stop_Pct'])
    for r in righe:
        prezzo = float(r.get('prezzo') or 0)
        sl_pct = float(ep.get('sl_pct') or 0)
        tp_pct = float(ep.get('tp_pct') or 0)
        ts_pct = ep.get('ts_pct', '')
        sl_price = round(prezzo * (1 - sl_pct / 100), 4) if prezzo and sl_pct else ''
        tp_price = round(prezzo * (1 + tp_pct / 100), 4) if prezzo and tp_pct else ''
        w.writerow([
            r.get('ticker', ''), r.get('nome', ''), r.get('mercato', ''),
            r.get('valuta', ''), r.get('prezzo', ''),
            r.get('quantita', ''), r.get('controvalore', ''),
            ep.get('tipo_ordine', 'MKT'), ep.get('prezzo_limite', ''),
            sl_price, tp_price, ts_pct,
        ])
    return buf.getvalue()


# ─── PRICE LOOKUP ────────────────────────────────────────────────────────────

def get_live_prices(tickers: list) -> dict:
    """
    Recupera prezzi live da yfinance per lista di ticker.
    Returns: {TICKER: {price, currency, name, exchange, change_pct, change_abs}}
    """
    results = {}
    if not _YF_OK:
        return {t.upper(): {'price': None, 'currency': 'N/D', 'name': t, 'exchange': 'N/D',
                            'change_pct': None, 'change_abs': None}
                for t in tickers if t.strip()}

    for raw in tickers:
        t = raw.strip().upper()
        if not t:
            continue
        try:
            obj = yf.Ticker(t)
            price = None
            currency = 'N/D'
            name = t
            exchange = 'N/D'
            change_pct = None
            change_abs = None
            try:
                fi = obj.fast_info
                price = fi.last_price
                currency = fi.currency or 'N/D'
                prev_close = getattr(fi, 'previous_close', None)
                if price and prev_close:
                    change_abs = round(float(price) - float(prev_close), 4)
                    change_pct = round(change_abs / float(prev_close) * 100, 2)
            except Exception:
                pass
            # Chiama info (lento) solo se fast_info non ha dato il prezzo
            if not price:
                try:
                    info = obj.info
                    price = (info.get('regularMarketPrice') or
                             info.get('currentPrice') or
                             info.get('previousClose'))
                    if change_pct is None:
                        raw_chg = info.get('regularMarketChangePercent')
                        if raw_chg is not None:
                            change_pct = round(float(raw_chg), 2)
                        raw_abs = info.get('regularMarketChange')
                        if raw_abs is not None:
                            change_abs = round(float(raw_abs), 4)
                    if currency == 'N/D':
                        currency = info.get('currency', 'N/D')
                    name     = info.get('shortName') or info.get('longName') or t
                    exchange = info.get('exchange', 'N/D')
                except Exception:
                    pass
            results[t] = {
                'price':      round(float(price), 4) if price else None,
                'currency':   currency,
                'name':       name,
                'exchange':   exchange,
                'change_pct': change_pct,
                'change_abs': change_abs,
            }
        except Exception:
            results[t] = {'price': None, 'currency': 'N/D', 'name': t, 'exchange': 'N/D',
                          'change_pct': None, 'change_abs': None}
    return results


# ─── EMAIL HTML GENERATOR ────────────────────────────────────────────────────

def _fmt(v, dec=2):
    try:
        return f'{float(v):,.{dec}f}'
    except Exception:
        return str(v)


def genera_email_html(ordine: dict) -> str:
    """
    Genera HTML professionale per email al partner bancario.

    ordine = {
        cliente_nome   : str,
        data           : str,          # DD/MM/YYYY HH:MM
        riferimento    : str,          # ORD-YYYYMMDD-XXX
        nome_gestore   : str,
        bank_nome      : str,
        bank_iban      : str,
        note           : str,
        righe          : [{ticker, nome, mercato, valuta, prezzo, quantita, controvalore}],
        anagrafica     : {indirizzo, cap, citta, paese, codice_fiscale, p_iva, telefono},
        exec_params    : {tipo_strumento, tipo_ordine, prezzo_limite, validita,
                          validita_data, conto, sl_pct, tp_pct, ts_pct}  (opzionale)
    }
    """
    ep = ordine.get('exec_params') or {}
    nome_gestore = ordine.get('nome_gestore', '') or ''
    bank_iban    = ordine.get('bank_iban', '') or ''

    # ── Sezione esecuzione ──────────────────────────────────────────────────
    tipo_strumento = ep.get('tipo_strumento', 'AZIONE')
    tipo_ordine    = ep.get('tipo_ordine', 'MKT')
    prezzo_limite  = ep.get('prezzo_limite', '')
    validita       = ep.get('validita', 'DAY')
    validita_data  = ep.get('validita_data', '')
    conto          = ep.get('conto', '')

    ordine_label = 'Al Meglio (Market)' if tipo_ordine == 'MKT' else f'Con Limite di Prezzo (Limit) — {prezzo_limite}'
    validita_label = {'DAY': 'Al Giorno', 'GTC': 'Good Till Cancelled (GTC)'}.get(validita, f'Fino al {validita_data}')

    exec_block = f"""
  <div style="background:#f7fafc;border:1px solid #e2e8f0;border-top:none;padding:18px 32px">
    <h2 style="margin:0 0 14px;color:#1a365d;font-size:13px;font-weight:700;
               text-transform:uppercase;letter-spacing:1px;
               border-bottom:2px solid #4a90d9;padding-bottom:8px">
      2. Parametri di Esecuzione
    </h2>
    <table style="width:100%;font-size:13px"><tr>
      <td style="padding:4px 16px 4px 0;width:25%">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:.8px">Tipologia Strumento</div>
        <div style="font-weight:700;color:#2d3748;margin-top:3px">{tipo_strumento}</div>
      </td>
      <td style="padding:4px 16px 4px 0;width:35%">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:.8px">Tipo di Ordine</div>
        <div style="font-weight:700;color:#2d3748;margin-top:3px">{'☐' if tipo_ordine=='LMT' else '☑'} Al Meglio (Market) &nbsp;&nbsp; {'☑' if tipo_ordine=='LMT' else '☐'} Con Limite di Prezzo</div>
        {f'<div style="color:#e53e3e;font-weight:700;font-size:14px;margin-top:4px">Limite: {prezzo_limite}</div>' if tipo_ordine == 'LMT' and prezzo_limite else ''}
      </td>
      <td style="padding:4px 16px 4px 0;width:25%">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:.8px">Validità Ordine</div>
        <div style="font-weight:700;color:#2d3748;margin-top:3px">{validita_label}</div>
      </td>
      <td style="padding:4px 0">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:.8px">Conto di Appoggio</div>
        <div style="font-weight:700;color:#2d3748;margin-top:3px">{conto or '—'}</div>
      </td>
    </tr></table>
  </div>"""

    # ── Anagrafica cliente ──────────────────────────────────────────────────
    ag = ordine.get('anagrafica') or {}
    _ag_indirizzo = ', '.join(filter(None, [
        ag.get('indirizzo',''), ag.get('cap',''), ag.get('citta',''), ag.get('paese','')
    ]))
    _ag_cf    = ag.get('codice_fiscale','') or ag.get('p_iva','')
    _ag_tel   = ag.get('telefono','')
    _ag_piva  = ag.get('p_iva','') if ag.get('p_iva') and ag.get('p_iva') != _ag_cf else ''
    _ag_rows = ''
    if _ag_indirizzo:
        _ag_rows += f'<tr><td style="padding:4px 16px 4px 0;color:#718096;font-size:11px;width:160px">Indirizzo</td><td style="font-weight:600;color:#2d3748;font-size:12px">{_ag_indirizzo}</td></tr>'
    if _ag_cf:
        _ag_rows += f'<tr><td style="padding:4px 16px 4px 0;color:#718096;font-size:11px">C.F. / NIE</td><td style="font-weight:600;color:#2d3748;font-size:12px">{_ag_cf}</td></tr>'
    if _ag_piva:
        _ag_rows += f'<tr><td style="padding:4px 16px 4px 0;color:#718096;font-size:11px">P.IVA</td><td style="font-weight:600;color:#2d3748;font-size:12px">{_ag_piva}</td></tr>'
    if _ag_tel:
        _ag_rows += f'<tr><td style="padding:4px 16px 4px 0;color:#718096;font-size:11px">Telefono</td><td style="font-weight:600;color:#2d3748;font-size:12px">{_ag_tel}</td></tr>'
    anagrafica_block = f"""
  <div style="background:#f7f7f7;border:1px solid #e2e8f0;border-top:none;padding:18px 32px">
    <h2 style="margin:0 0 12px;color:#1a365d;font-size:13px;font-weight:700;
               text-transform:uppercase;letter-spacing:1px;
               border-bottom:2px solid #a0aec0;padding-bottom:8px">
      Dati del Cliente Ordinante
    </h2>
    <table style="font-size:12px">
      <tr><td style="padding:4px 16px 4px 0;color:#718096;font-size:11px;width:160px">Cliente</td>
          <td style="font-weight:700;color:#1a365d;font-size:13px">{ordine['cliente_nome']}</td></tr>
      {_ag_rows}
    </table>
    <p style="margin:14px 0 0;font-size:11px;color:#718096">
      <em>Firma del cliente: ___________________________</em>
    </p>
  </div>"""

    # ── Sezione titoli ──────────────────────────────────────────────────────
    show_risk = any(
        float(r.get('sl_pct') or 0) or float(r.get('tp_pct') or 0)
        for r in ordine.get('righe', [])
    )

    righe_html = ''
    totals: dict = {}

    for r in ordine.get('righe', []):
        valuta  = r.get('valuta', '')
        contro  = float(r.get('controvalore') or 0)
        prezzo  = float(r.get('prezzo') or 0)
        totals[valuta] = totals.get(valuta, 0) + contro

        prezzo_str = f'{valuta}&nbsp;{_fmt(prezzo, 4)}' if prezzo else 'N/D'
        contro_str = f'{valuta}&nbsp;{_fmt(contro)}' if contro else 'N/D'
        qty_fmt    = f'{int(r.get("quantita", 0)):,}'

        r_sl = float(r.get('sl_pct') or 0)
        r_tp = float(r.get('tp_pct') or 0)
        sl_str = f'{valuta}&nbsp;{_fmt(prezzo*(1-r_sl/100),4)}' if prezzo and r_sl else '—'
        tp_str = f'{valuta}&nbsp;{_fmt(prezzo*(1+r_tp/100),4)}' if prezzo and r_tp else '—'

        risk_cells = (
            f'<td style="padding:9px 10px;border-bottom:1px solid #e2e8f0;text-align:right;font-size:12px;color:#c53030">{sl_str}</td>'
            f'<td style="padding:9px 10px;border-bottom:1px solid #e2e8f0;text-align:right;font-size:12px;color:#276749">{tp_str}</td>'
        ) if show_risk else ''

        righe_html += f"""
        <tr>
          <td style="padding:9px 10px;border-bottom:1px solid #e2e8f0;
                     font-family:'Courier New',monospace;font-weight:700;
                     color:#1a365d;font-size:13px">{r.get('ticker','')}</td>
          <td style="padding:9px 10px;border-bottom:1px solid #e2e8f0;font-size:13px">{r.get('nome','')}</td>
          <td style="padding:9px 10px;border-bottom:1px solid #e2e8f0;font-size:11px;
                     color:#718096">{r.get('mercato','')}</td>
          <td style="padding:9px 10px;border-bottom:1px solid #e2e8f0;
                     text-align:right;font-size:13px">{prezzo_str}</td>
          <td style="padding:9px 10px;border-bottom:1px solid #e2e8f0;
                     text-align:right;font-weight:700;font-size:14px">{qty_fmt}</td>
          <td style="padding:9px 10px;border-bottom:1px solid #e2e8f0;
                     text-align:right;font-weight:700;font-size:14px;
                     color:#2d3748">{contro_str}</td>
          {risk_cells}
        </tr>"""

    risk_headers = (
        '<th style="padding:9px 10px;text-align:right;color:#c53030;font-size:10px;text-transform:uppercase;letter-spacing:1px">Stop Loss</th>'
        '<th style="padding:9px 10px;text-align:right;color:#276749;font-size:10px;text-transform:uppercase;letter-spacing:1px">Take Profit</th>'
    ) if show_risk else ''

    totali_colspan = 7 if show_risk else 5
    totali_rows = ''
    for curr, v in totals.items():
        totali_rows += f"""
        <tr style="background:#1a365d">
          <td colspan="{totali_colspan}" style="padding:12px 14px;color:#fff;font-weight:700;
                                  text-align:right;font-size:13px;
                                  text-transform:uppercase;letter-spacing:.5px">
            Totale {curr}
          </td>
          <td style="padding:12px 14px;color:#f6ad55;font-weight:700;
                     text-align:right;font-size:17px;
                     font-family:'Courier New',monospace">
            {curr}&nbsp;{_fmt(v)}
          </td>
        </tr>"""

    note_block = ''
    if ordine.get('note'):
        note_block = f"""
      <div style="margin-top:20px;padding:14px 18px;background:#fffbf0;
                  border-left:4px solid #f6ad55;border-radius:4px">
        <strong style="color:#744210;font-size:12px">NOTE DEL CLIENTE:</strong>
        <p style="margin:6px 0 0;color:#2d3748;font-size:13px">{ordine['note']}</p>
      </div>"""

    # ── Sezione rischio per singolo titolo ──────────────────────────────────
    risk_block = ''
    if show_risk:
        risk_detail_rows = ''
        for r in ordine.get('righe', []):
            r_sl = float(r.get('sl_pct') or 0)
            r_tp = float(r.get('tp_pct') or 0)
            if not r_sl and not r_tp:
                continue
            r_prezzo = float(r.get('prezzo') or 0)
            r_valuta = r.get('valuta', '')
            sl_price = f'{r_valuta}&nbsp;{_fmt(r_prezzo*(1-r_sl/100),4)}' if r_prezzo and r_sl else '—'
            tp_price = f'{r_valuta}&nbsp;{_fmt(r_prezzo*(1+r_tp/100),4)}' if r_prezzo and r_tp else '—'
            risk_detail_rows += f"""
        <tr>
          <td style="padding:7px 10px;border-bottom:1px solid #fbd38d44;
                     font-family:'Courier New',monospace;font-weight:700;color:#744210">{r.get('ticker','')}</td>
          <td style="padding:7px 10px;border-bottom:1px solid #fbd38d44;font-size:12px;color:#2d3748">{r.get('nome','')}</td>
          <td style="padding:7px 10px;border-bottom:1px solid #fbd38d44;text-align:right;font-weight:700;color:#c53030;font-size:12px">
            {f'{r_sl}%' if r_sl else '—'}<br><span style="font-size:10px;color:#a0aec0">{sl_price}</span></td>
          <td style="padding:7px 10px;border-bottom:1px solid #fbd38d44;text-align:right;font-weight:700;color:#276749;font-size:12px">
            {f'{r_tp}%' if r_tp else '—'}<br><span style="font-size:10px;color:#a0aec0">{tp_price}</span></td>
        </tr>"""
        risk_block = f"""
  <div style="background:#fff8f0;border:1px solid #fbd38d;border-top:none;padding:18px 32px">
    <h2 style="margin:0 0 12px;color:#744210;font-size:13px;font-weight:700;
               text-transform:uppercase;letter-spacing:1px;
               border-bottom:2px solid #f6ad55;padding-bottom:8px">
      3. Gestione del Rischio — Stop Loss / Take Profit
    </h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="background:#fef3e2">
        <th style="padding:7px 10px;text-align:left;color:#744210;font-size:10px;text-transform:uppercase;letter-spacing:1px">Ticker</th>
        <th style="padding:7px 10px;text-align:left;color:#744210;font-size:10px;text-transform:uppercase;letter-spacing:1px">Denominazione</th>
        <th style="padding:7px 10px;text-align:right;color:#c53030;font-size:10px;text-transform:uppercase;letter-spacing:1px">Stop Loss</th>
        <th style="padding:7px 10px;text-align:right;color:#276749;font-size:10px;text-transform:uppercase;letter-spacing:1px">Take Profit</th>
      </tr></thead>
      <tbody>{risk_detail_rows}</tbody>
    </table>
    <p style="margin:10px 0 0;font-size:11px;color:#a0aec0">
      Le istruzioni di protezione devono essere impostate autonomamente dal cliente sulla propria piattaforma bancaria.
    </p>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:Arial,sans-serif">
<div style="max-width:760px;margin:0 auto;padding:28px 16px">

  <div style="background:linear-gradient(135deg,#1a365d 0%,#2b6cb0 100%);
              padding:20px 32px;border-radius:10px 10px 0 0">
    <div style="color:#90cdf4;font-size:12px;letter-spacing:1px;text-transform:uppercase">
      MODULO D&rsquo;ORDINE DI ACQUISTO PRODOTTI FINANZIARI
    </div>
  </div>

  <div style="background:#ebf8ff;border:1px solid #bee3f8;border-top:none;padding:16px 32px">
    <h2 style="margin:0 0 10px;color:#1a365d;font-size:13px;font-weight:700;
               text-transform:uppercase;letter-spacing:1px;
               border-bottom:2px solid #2b6cb0;padding-bottom:8px">
      1. Dati Identificativi dell'Operazione
    </h2>
    <table style="width:100%;margin-bottom:10px"><tr>
      <td style="padding-right:24px">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:1px">Cliente</div>
        <div style="font-weight:700;color:#1a365d;font-size:14px;margin-top:3px">{ordine['cliente_nome']}</div>
      </td>
      <td style="padding-right:24px">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:1px">Data / Ora Richiesta</div>
        <div style="font-weight:700;color:#1a365d;font-size:14px;margin-top:3px">{ordine['data']}</div>
      </td>
      <td style="padding-right:24px">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:1px">Riferimento Ordine</div>
        <div style="font-weight:700;color:#1a365d;font-size:14px;margin-top:3px;
                    font-family:'Courier New',monospace">{ordine['riferimento']}</div>
      </td>
      <td>
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:1px">Conto di Appoggio</div>
        <div style="font-weight:700;color:#1a365d;font-size:14px;margin-top:3px">{conto or '—'}</div>
      </td>
    </tr></table>
    <table style="width:100%"><tr>
      <td style="padding-right:24px">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:1px">Banca / Intermediario</div>
        <div style="font-weight:700;color:#1a365d;font-size:13px;margin-top:3px">{ordine.get('bank_nome','') or '—'}</div>
      </td>
      <td style="padding-right:24px">
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:1px">Nome Gestore</div>
        <div style="font-weight:700;color:#1a365d;font-size:13px;margin-top:3px">{nome_gestore or '—'}</div>
      </td>
      <td>
        <div style="font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:1px">IBAN Conto Cliente</div>
        <div style="font-weight:700;color:#1a365d;font-size:13px;margin-top:3px;font-family:'Courier New',monospace">{bank_iban or '—'}</div>
      </td>
    </tr></table>
  </div>

  {exec_block}

  <div style="background:#fff;border:1px solid #e2e8f0;border-top:none;padding:24px 32px">
    <h2 style="margin:0 0 16px;color:#1a365d;font-size:13px;font-weight:700;
               text-transform:uppercase;letter-spacing:1px;
               border-bottom:2px solid #2b6cb0;padding-bottom:10px">
      {'3' if not show_risk else '4'}. Dettaglio Titoli da Acquistare
    </h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="background:#edf2f7">
        <th style="padding:9px 10px;text-align:left;color:#4a5568;font-size:10px;
                   text-transform:uppercase;letter-spacing:1px">Ticker</th>
        <th style="padding:9px 10px;text-align:left;color:#4a5568;font-size:10px;
                   text-transform:uppercase;letter-spacing:1px">Denominazione</th>
        <th style="padding:9px 10px;text-align:left;color:#4a5568;font-size:10px;
                   text-transform:uppercase;letter-spacing:1px">Mercato</th>
        <th style="padding:9px 10px;text-align:right;color:#4a5568;font-size:10px;
                   text-transform:uppercase;letter-spacing:1px">Prezzo Rif.</th>
        <th style="padding:9px 10px;text-align:right;color:#4a5568;font-size:10px;
                   text-transform:uppercase;letter-spacing:1px">Quantita</th>
        <th style="padding:9px 10px;text-align:right;color:#4a5568;font-size:10px;
                   text-transform:uppercase;letter-spacing:1px">Controvalore</th>
        {risk_headers}
      </tr></thead>
      <tbody>{righe_html}</tbody>
      <tfoot>{totali_rows}</tfoot>
    </table>
    {note_block}
  </div>

  {risk_block}

  {anagrafica_block}

  <div style="background:#fff5f5;border:1px solid #fed7d7;border-top:none;
              padding:16px 32px;border-radius:0 0 10px 10px">
    <p style="margin:0;font-size:11px;color:#c53030;line-height:1.7">
      <strong>AVVERTENZE MiFID II &mdash;</strong>
      Le presenti istruzioni sono predisposte autonomamente dal cliente a titolo personale
      e non costituiscono consulenza finanziaria, gestione patrimoniale ne raccomandazione di investimento.
      Robot Trader 2026 fornisce esclusivamente un servizio di screening quantitativo informativo
      ai sensi della Direttiva MiFID II e non svolge attivita di esecuzione ordini ne di ricezione e
      trasmissione di ordini. I prezzi indicati sono di riferimento al momento della generazione
      e non costituiscono prezzi garantiti di esecuzione. Il cliente e l&rsquo;unico responsabile
      delle istruzioni impartite al proprio intermediario bancario.
    </p>
    <p style="margin:8px 0 0;font-size:10px;color:#a0aec0">
      Ordine effettuato con Robot Trader 2026 &mdash; {ordine['data']}
    </p>
  </div>

</div>
</body></html>"""


# ─── SMTP SEND ───────────────────────────────────────────────────────────────

def invia_email_ordine(bank_email: str, oggetto: str, html_body: str,
                       cliente_email: str = '') -> tuple:
    """
    Invia email ordine via Brevo SMTP.
    Returns: (ok: bool, msg: str)
    """
    if not BREVO_SMTP_LOGIN or not BREVO_SMTP_PASSWORD:
        return False, 'BREVO_SMTP_LOGIN / PASSWORD non configurati'
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = oggetto
        msg['From']    = f'Fuerte Screener <{BREVO_SMTP_LOGIN}>'
        msg['To']      = bank_email
        if cliente_email:
            msg['Cc'] = cliente_email
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        recipients = [bank_email] + ([cliente_email] if cliente_email else [])
        with smtplib.SMTP(BREVO_SMTP_HOST, BREVO_SMTP_PORT, timeout=15) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
            srv.sendmail(BREVO_SMTP_LOGIN, recipients, msg.as_bytes())
        return True, f'Email inviata a {bank_email}'
    except Exception as e:
        return False, str(e)
