# -*- coding: utf-8 -*-
"""
FETCH JUSTETF UNIVERSE - Robot Trader 2026
==========================================
Scarica tutti gli ETF UCITS da justETF (sitemap) e costruisce
etf_universe_cache.json con: isin, nome, ticker, TER, tipo (ACC/DIST),
replica (Fisica/Sintetica).

USO:
  python fetch_justetf_universe.py              # scrape completo (~2h)
  python fetch_justetf_universe.py --update     # aggiorna solo ISIN mancanti
  python fetch_justetf_universe.py --stats      # mostra statistiche cache
"""

import urllib.request
import urllib.error
import http.cookiejar
import re
import json
import os
import sys
import time
import random
from datetime import datetime

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, 'etf_universe_cache.json')

SITEMAP_URL  = 'https://www.justetf.com/sitemap5.xml'
HOME_URL     = 'https://www.justetf.com/en/'

# Exchange preference per il ticker yfinance
EXCHANGE_PRIORITY = ['L', 'DE', 'AS', 'MI', 'PA', 'SW', 'ST', 'HE', 'CO', 'OL', 'LI', 'BR', 'LS', 'MC']

# Pausa tra richieste — più lenta per non far scattare il ban
REQUEST_DELAY_MIN = 1.5
REQUEST_DELAY_MAX = 3.5

# Pausa extra ogni N richieste (simula pausa umana)
BATCH_SIZE       = 50    # salva cache ogni N
LONG_PAUSE_EVERY = 200   # pausa lunga ogni N richieste
LONG_PAUSE_MIN   = 20
LONG_PAUSE_MAX   = 40

# ISIN domicilio UCITS europei
EU_PREFIXES = ('IE', 'LU', 'FR', 'DE', 'GB', 'CH', 'AT', 'BE', 'NL', 'ES', 'IT',
               'DK', 'SE', 'FI', 'NO', 'PL', 'CZ', 'HU')

# ── Sessione HTTP con cookie ──────────────────────────────────────────────────
_cookie_jar = http.cookiejar.CookieJar()
_opener     = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookie_jar))

def _headers(referer=None):
    h = {
        'User-Agent':      ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) '
                            'Chrome/124.0.0.0 Safari/537.36'),
        'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,'
                           'image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection':      'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest':  'document',
        'Sec-Fetch-Mode':  'navigate',
        'Sec-Fetch-Site':  'same-origin' if referer else 'none',
        'Sec-Fetch-User':  '?1',
    }
    if referer:
        h['Referer'] = referer
    return h


def _session_init():
    """Visita la homepage per ottenere cookie di sessione/GDPR."""
    try:
        req = urllib.request.Request(HOME_URL, headers=_headers())
        with _opener.open(req, timeout=15) as r:
            r.read()
        print("[Session] Cookie di sessione acquisiti", flush=True)
        time.sleep(random.uniform(2, 4))
    except Exception as e:
        print(f"[Session] Avviso: homepage non raggiungibile ({e})", flush=True)


def _get(url, timeout=20, retries=4):
    """Fetch con sessione, Referer e retry su 403/429/5xx."""
    referer = 'https://www.justetf.com/en/find-etf.html'
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=_headers(referer))
            with _opener.open(req, timeout=timeout) as r:
                raw = r.read()
            # urllib gestisce gzip via Accept-Encoding ma non sempre decomprime
            # automaticamente — forziamo la decodifica manuale
            content_enc = ''
            if hasattr(r, 'headers'):
                content_enc = r.headers.get('Content-Encoding', '')
            if 'gzip' in content_enc:
                import gzip
                return gzip.decompress(raw).decode('utf-8', errors='ignore')
            if 'br' in content_enc:
                try:
                    import brotli
                    return brotli.decompress(raw).decode('utf-8', errors='ignore')
                except ImportError:
                    pass
            return raw.decode('utf-8', errors='ignore')

        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                wait = random.uniform(15, 30) * attempt
                print(f"  [Retry {attempt}/{retries}] HTTP {e.code} — attendo {wait:.0f}s...",
                      flush=True)
                time.sleep(wait)
                if attempt == 2:
                    # Rinnova sessione a metà dei retry
                    _session_init()
            elif e.code >= 500:
                time.sleep(random.uniform(5, 10))
            else:
                raise
        except Exception as e:
            if attempt < retries:
                time.sleep(random.uniform(3, 8))
            else:
                raise
    raise RuntimeError(f"Impossibile scaricare {url} dopo {retries} tentativi")


def fetch_all_isins():
    """Legge tutti gli ISIN UCITS dalla sitemap justETF."""
    print(f"Scarico sitemap: {SITEMAP_URL}", flush=True)
    body = _get(SITEMAP_URL)
    urls_en = re.findall(
        r'<loc>(https://www\.justetf\.com/en/etf-profile\.html\?isin=[A-Z0-9]+)</loc>',
        body
    )
    isins = list(dict.fromkeys(
        re.findall(r'isin=([A-Z]{2}[A-Z0-9]{10})', ' '.join(urls_en))
    ))
    isins = [i for i in isins if i[:2] in EU_PREFIXES]
    print(f"ISIN UCITS trovati: {len(isins)}", flush=True)
    return isins


def parse_profile(isin, body):
    """Estrae dati dal profilo justETF di un ISIN."""

    name_m = re.search(r'<title>(.*?)(?:\s*\||\s*–)', body)
    name = name_m.group(1).strip() if name_m else ''

    # TER
    ter = None
    for pat in [
        r'([0-9]+[.,][0-9]+)\s*%\s*p\.a',
        r'expense[^%]{0,80}([0-9]+[.,][0-9]+)\s*%',
        r'TER[^%]{0,80}([0-9]+[.,][0-9]+)\s*%',
    ]:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            try:
                ter = float(m.group(1).replace(',', '.'))
                break
            except ValueError:
                pass

    # ACC / DIST
    is_acc = None
    dist_m = re.search(r'distribution-policy-value">\s*(Accumulating|Distributing)', body)
    if dist_m:
        is_acc = dist_m.group(1) == 'Accumulating'
    else:
        title_m = re.search(r'<title>(.*?)</title>', body)
        if title_m:
            t = title_m.group(1)
            if 'Accumulating' in t:
                is_acc = True
            elif 'Distributing' in t:
                is_acc = False

    # Replica
    is_physical = None
    repl_m = re.search(r'replication-value">\s*(Physical|Synthetic|Optimised)', body)
    if repl_m:
        is_physical = repl_m.group(1) == 'Physical'

    # Tickers
    tickers_found = re.findall(
        r'\b([A-Z0-9]{2,6})\.(L|DE|MI|AS|PA|SW|ST|HE|CO|OL|LI|BR|LS|MC)\b',
        body
    )
    seen = set()
    ticker_list = []
    for t, ext in tickers_found:
        full = f"{t}.{ext}"
        if full not in seen and len(t) >= 2:
            seen.add(full)
            ticker_list.append({'ticker': full, 'exchange': ext})

    preferred = None
    for ext in EXCHANGE_PRIORITY:
        for item in ticker_list:
            if item['exchange'] == ext:
                preferred = item['ticker']
                break
        if preferred:
            break

    incep_m = re.search(r'(\d{2}\.\d{2}\.\d{4})', body[:15000])
    inception = incep_m.group(1) if incep_m else None

    aum = None
    aum_m = re.search(r'EUR\s*([\d,\.]+)\s*(m|bn|billion|million)', body[:10000], re.IGNORECASE)
    if aum_m:
        try:
            val = float(aum_m.group(1).replace(',', ''))
            unit = aum_m.group(2).lower()
            aum = val * (1_000_000_000 if unit in ('bn', 'billion') else 1_000_000)
        except ValueError:
            pass

    return {
        'isin':             isin,
        'name':             name,
        'ter':              ter,
        'is_acc':           is_acc,
        'is_physical':      is_physical,
        'preferred_ticker': preferred,
        'all_tickers':      [item['ticker'] for item in ticker_list],
        'inception':        inception,
        'aum_eur':          aum,
        'fetched_at':       datetime.now().strftime('%Y-%m-%d'),
    }


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache):
    tmp = CACHE_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CACHE_FILE)


def print_stats(cache):
    total     = len(cache)
    errors    = sum(1 for v in cache.values() if v.get('error'))
    has_tick  = sum(1 for v in cache.values() if v.get('preferred_ticker'))
    has_ter   = sum(1 for v in cache.values() if v.get('ter') is not None)
    acc_only  = sum(1 for v in cache.values() if v.get('is_acc') is True)
    phys_only = sum(1 for v in cache.values() if v.get('is_physical') is True)
    ready     = sum(1 for v in cache.values()
                    if v.get('preferred_ticker') and v.get('ter') is not None
                    and v.get('is_acc') is True and v.get('is_physical') is True)
    print(f"\n{'='*55}")
    print(f"  ETF UNIVERSE CACHE — {CACHE_FILE}")
    print(f"{'='*55}")
    print(f"  ISIN totali in cache:                    {total:>5}")
    print(f"  Errori (403/timeout/altri):              {errors:>5}")
    print(f"  Con ticker yfinance:                     {has_tick:>5}")
    print(f"  Con TER disponibile:                     {has_ter:>5}")
    print(f"  Solo Accumulazione:                      {acc_only:>5}")
    print(f"  Solo Replica Fisica:                     {phys_only:>5}")
    print(f"  PRONTI (ACC+Fisica+TER+Ticker):          {ready:>5}")
    print(f"{'='*55}\n")


def main():
    mode_update = '--update' in sys.argv
    mode_stats  = '--stats'  in sys.argv

    cache = load_cache()

    if mode_stats:
        print_stats(cache)
        return

    # Acquisisce cookie di sessione prima di partire
    _session_init()

    isins = fetch_all_isins()

    if mode_update:
        # In update mode: riscrapi anche gli errori precedenti (potrebbero essere temporanei)
        isins = [i for i in isins if i not in cache or cache[i].get('error')]
        print(f"Modalità UPDATE: {len(isins)} ISIN da aggiornare", flush=True)
    else:
        print(f"Modalità FULL: {len(isins)} ISIN da scrapare", flush=True)

    total  = len(isins)
    errors = 0

    for idx, isin in enumerate(isins, 1):
        url = f"https://www.justetf.com/en/etf-profile.html?isin={isin}"
        try:
            body = _get(url)
            data = parse_profile(isin, body)
            cache[isin] = data

            ticker_str = data.get('preferred_ticker') or '—'
            ter_str    = f"{data['ter']:.2f}%" if data.get('ter') else '—'
            acc_str    = 'ACC' if data.get('is_acc') else ('DIST' if data.get('is_acc') is False else '?')
            print(f"  [{idx}/{total}] {isin}  {ticker_str:<12} TER:{ter_str:<7} {acc_str}  {data.get('name','')[:40]}",
                  flush=True)

        except Exception as e:
            errors += 1
            cache[isin] = {'isin': isin, 'error': str(e), 'fetched_at': datetime.now().strftime('%Y-%m-%d')}
            print(f"  [{idx}/{total}] {isin}  ERRORE: {e}", flush=True)

        # Salva ogni BATCH_SIZE ETF
        if idx % BATCH_SIZE == 0:
            save_cache(cache)
            print(f"  >>> Cache salvata ({idx}/{total}) — errori finora: {errors}", flush=True)

        # Pausa lunga ogni LONG_PAUSE_EVERY richieste (simula comportamento umano)
        if idx % LONG_PAUSE_EVERY == 0:
            pause = random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
            print(f"  >>> Pausa lunga {pause:.0f}s per evitare ban...", flush=True)
            time.sleep(pause)
            _session_init()  # rinnova cookie dopo la pausa
        else:
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

    save_cache(cache)
    print(f"\nScraping completato. Errori: {errors}/{total}", flush=True)
    print_stats(cache)


if __name__ == '__main__':
    main()
