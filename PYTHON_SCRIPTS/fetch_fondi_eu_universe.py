# -*- coding: utf-8 -*-
"""
FETCH FONDI EU UNIVERSE - Robot Trader 2026
===========================================
COME FUNZIONA (semplice):

  FASE 1 — 71 ISIN seed → cerca ticker su Yahoo Finance per ISIN
            (funziona per ~38% degli ISIN, principalmente FR/DE)

  FASE 2 — ~420 termini di ricerca libera → scansiona Yahoo Finance
            cercando "Amundi SICAV", "Pictet Water", "SICAV europe equity" ecc.
            Filtra: tieni solo i fondi con suffisso borsa europea (.F .PA .MI ...)
            Risultato atteso: 1.000-1.500 fondi unici aggiuntivi

  In entrambi i casi, per ogni ticker trovato chiama yfinance per
  recuperare TER, categoria, AUM, Morningstar rating.

USO:
  python fetch_fondi_eu_universe.py              # FASE 1 + FASE 2 (completo)
  python fetch_fondi_eu_universe.py --isin       # solo FASE 1 (ISIN seed)
  python fetch_fondi_eu_universe.py --discover   # solo FASE 2 (discovery termini)
  python fetch_fondi_eu_universe.py --update     # rielabora solo errori/mancanti
  python fetch_fondi_eu_universe.py --stats      # mostra statistiche cache
"""

import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import time
import random
from datetime import datetime

try:
    import yfinance as yf
    _YF_OK = True
except ImportError:
    _YF_OK = False
    print("WARNING: yfinance non installato: pip install yfinance", flush=True)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, 'fondi_eu_universe_cache.json')

REQUEST_DELAY_MIN = 1.2
REQUEST_DELAY_MAX = 2.8
BATCH_SIZE        = 25

# Suffissi Yahoo Finance per borse europee
# Un fondo e' "EU" se il suo ticker finisce con uno di questi
EU_SUFFIXES = {
    '.F',   # Frankfurt
    '.MU',  # Munich
    '.PA',  # Paris
    '.MI',  # Milan
    '.L',   # London
    '.AS',  # Amsterdam
    '.SW',  # Switzerland
    '.ST',  # Stockholm
    '.CO',  # Copenhagen
    '.HE',  # Helsinki
    '.OL',  # Oslo
    '.VI',  # Vienna
    '.BR',  # Brussels
    '.LS',  # Lisbon
    '.MC',  # Madrid
    '.WA',  # Warsaw
    '.BD',  # Budapest
    '.DE',  # Dublin/Ireland
    '.IR',  # Ireland alt
    '.BE',  # Belgium alt
    '.VX',  # Swiss alt
}

# ── FASE 1: ISINs seed di fondi UCITS europei di riferimento ─────────────────
EU_SEED_ISINS = [
    # Carmignac (France)
    'FR0010135103',  # Carmignac Patrimoine A EUR acc
    'FR0007078811',  # Carmignac Investissement A EUR acc
    'FR0010148981',  # Carmignac Commodities A EUR acc
    'FR0010149302',  # Carmignac Emergents A EUR acc
    'FR0010510800',  # Carmignac Portfolio Grande Europe A EUR acc
    # DWS (Germany)
    'DE0009848119',  # DWS Top Dividende LD
    'DE0008474511',  # DWS Deutschland LC
    'DE0009769869',  # DWS Akkumula
    'LU0003549028',  # DWS Global Growth LD
    'LU0145634076',  # DWS Invest Global Infrastructure LC
    'DE0008479452',  # DWS Vermögensbildungsfonds I
    # Union Investment (Germany)
    'DE0009750273',  # UniGlobal
    'DE0009750117',  # UniEuropa
    'DE0008007073',  # UniDividendenAss A
    # Pictet (Luxembourg)
    'LU0094836167',  # Pictet-Water P dy EUR
    'LU0128427002',  # Pictet-Security P dy EUR
    'LU0503635038',  # Pictet-Clean Energy Transition P EUR
    'LU0386882277',  # Pictet-Robotics P EUR
    'LU0341009267',  # Pictet-Premium Brands P EUR
    # Schroder ISF (Luxembourg)
    'LU0106235521',  # Schroder ISF Global Equity A Acc EUR
    'LU0012062452',  # Schroder ISF European Equity A Acc EUR
    'LU0557289705',  # Schroder ISF Emerging Markets A Acc EUR
    # Nordea (Luxembourg)
    'LU0141799501',  # Nordea 1 North American Stars BI EUR
    'LU0255639139',  # Nordea 1 European High Yield BI EUR
    'LU0861579265',  # Nordea 1 Global Climate and Environment BI EUR
    'LU0141799329',  # Nordea 1 European Stars Equity BI EUR
    # Robeco (Netherlands/Luxembourg)
    'LU0234938657',  # Robeco BP Global Premium Equities D EUR
    'LU0187077449',  # Robeco Sustainable Global Stars D EUR
    'LU0329200929',  # Robeco High Yield Bonds DH EUR
    # Comgest (France/Ireland)
    'IE0004766014',  # Comgest Growth Europe EUR Acc
    'IE0004766345',  # Comgest Growth World EUR Acc
    'IE00B3Z9HF45',  # Comgest Growth Emerging Markets EUR Acc
    # M&G (UK)
    'GB0030932676',  # M&G Recovery Fund A
    'GB0031288359',  # M&G Global Leaders Fund A
    'GB00B3LGQ083',  # M&G Global Dividend Fund A
    'GB00B1VMCY93',  # M&G Optimal Income Fund A
    # Fidelity International (Luxembourg)
    'LU0048578792',  # Fidelity Funds European High Yield A EUR
    'LU0251127410',  # Fidelity Funds European Growth A EUR
    'LU0261948904',  # Fidelity Funds World Fund A USD
    'LU0114720869',  # Fidelity Funds Pacific A USD
    # Franklin Templeton (Luxembourg)
    'LU0070683474',  # Templeton Global Bond A (Ydis) USD
    'LU0114760746',  # Franklin European Growth A EUR
    'LU0229946628',  # Franklin Global Growth and Value A USD
    # Allianz GI (Luxembourg)
    'LU0256839939',  # Allianz Interglobal A EUR
    'LU0082928562',  # Allianz European Equity A EUR
    # BNP Paribas AM
    'FR0000170052',  # BNP Paribas Actions Europe Croissance C
    'LU0823400465',  # BNP Paribas Funds Europe Growth Classic C
    # AXA Investment Managers
    'FR0000447823',  # AXA Valeurs du Monde A
    'LU0087656023',  # AXA WF Framlington Europe A EUR
    # Amundi
    'FR0010321810',  # Amundi Actions Euro ISR C
    'LU0417497552',  # Amundi Funds Pioneer US Equity A EUR C
    # Aberdeen/abrdn
    'LU0231460373',  # abrdn Global Equity A Acc
    'LU0012037694',  # abrdn European Equity A Acc EUR
    # Janus Henderson
    'LU0011889846',  # Janus Henderson Horizon Pan European Equity A2 EUR
    'LU0256892471',  # Janus Henderson Horizon Global Technology Leaders A2 USD
    # Invesco
    'LU0243957239',  # Invesco Pan European High Income A qd EUR
    # T. Rowe Price
    'LU0133083469',  # T. Rowe Price Funds Global Equity A EUR
    'LU0174119429',  # T. Rowe Price Funds US Large Cap Growth Equity A USD
    # JPMorgan AM
    'LU0210527450',  # JPMorgan Funds Global Select Equity A EUR
    'LU0048836161',  # JPMorgan Funds America Equity A USD
    # BlackRock (Luxembourg)
    'LU0171289902',  # BlackRock GF World Healthscience A2 USD
    'LU0082031725',  # BlackRock GF World Gold A2 USD
    # Goldman Sachs AM
    'LU0073232471',  # Goldman Sachs Japan Portfolio Base Acc USD
    'LU0234588895',  # Goldman Sachs EM Equity Portfolio Base Acc USD
    # Baillie Gifford
    'IE0030786142',  # Baillie Gifford WW Long Term Global Growth A EUR Acc
    # HSBC AM
    'LU0161684885',  # HSBC GIF Asia ex Japan Equity A
    # Flossbach von Storch (Germany)
    'LU0323578657',  # Flossbach von Storch SICAV Multiple Opportunities R
    'LU0261578657',  # Flossbach von Storch SICAV Bond Opportunities R
    # Threadneedle (UK)
    'GB0002771383',  # Threadneedle European Select Fund
    'GB00B8169B46',  # Threadneedle Global Select Fund
]

# ── FASE 2: termini di ricerca libera per scoprire fondi UCITS EU ────────────
# Ogni termine viene cercato su Yahoo Finance.
# Yahoo restituisce fino a 8 risultati per termine.
# Teniamo solo quelli con suffisso borsa europea (EU_SUFFIXES).
# Con 420 termini x media 3-4 fondi EU = ~1.200-1.700 fondi unici.
DISCOVERY_TERMS = [
    # ── Amundi (France/Luxembourg — il piu' grande gestore EU) ──────────────
    'Amundi Funds equity', 'Amundi SICAV global', 'Amundi Select equity',
    'Amundi Europe equity', 'Amundi bond SICAV', 'Amundi Responsible',
    'Amundi Pioneer', 'Amundi convertible', 'Amundi emerging markets',
    'Amundi actions euro', 'Amundi patrimoine',

    # ── DWS (Germany/Luxembourg) ────────────────────────────────────────────
    'DWS Invest equity', 'DWS Top Dividende', 'DWS Global equity',
    'DWS Concept', 'DWS Akkumula', 'DWS Deutschland fund',
    'DWS European opportunities', 'DWS Fixed Income', 'DWS Balance',

    # ── Pictet (Luxembourg/Switzerland) ─────────────────────────────────────
    'Pictet Water fund', 'Pictet Security fund', 'Pictet Robotics fund',
    'Pictet Premium Brands', 'Pictet Digital', 'Pictet Clean Energy',
    'Pictet Biotech fund', 'Pictet Global Megatrend', 'Pictet Europe',
    'Pictet Emerging Markets', 'Pictet Total Return', 'Pictet Short Term',
    'Pictet Nutrition', 'Pictet Health', 'Pictet Timber',

    # ── Schroder (Luxembourg) ────────────────────────────────────────────────
    'Schroder ISF European', 'Schroder ISF Global', 'Schroder ISF Emerging',
    'Schroder ISF Asian', 'Schroder ISF Bond', 'Schroder ISF US',
    'Schroder ISF Income', 'Schroder ISF QEP', 'Schroder ISF Sustainable',

    # ── Nordea (Luxembourg) ──────────────────────────────────────────────────
    'Nordea 1 European equity', 'Nordea 1 Global equity', 'Nordea 1 Emerging',
    'Nordea 1 Bond', 'Nordea 1 North American', 'Nordea 1 Asian',
    'Nordea stable return', 'Nordea 1 Balanced', 'Nordea 1 Climate',

    # ── Robeco (Luxembourg) ──────────────────────────────────────────────────
    'Robeco Premium Equities', 'Robeco Sustainable', 'Robeco Global equity',
    'Robeco European', 'Robeco Emerging equity', 'Robeco High Yield',
    'Robeco Capital Growth', 'Robeco Financial', 'Robeco BP Conservative',

    # ── Carmignac (France/Luxembourg) ───────────────────────────────────────
    'Carmignac Patrimoine fund', 'Carmignac Portfolio', 'Carmignac Investissement',
    'Carmignac Emergents', 'Carmignac Commodities', 'Carmignac Bond fund',
    'Carmignac Court Terme', 'Carmignac Absolute',

    # ── Comgest (France/Ireland) ─────────────────────────────────────────────
    'Comgest Growth Europe', 'Comgest Growth World', 'Comgest Growth Emerging',
    'Comgest Growth Americas', 'Comgest Growth Asia', 'Comgest Growth Japan',

    # ── Fidelity International (Luxembourg) ─────────────────────────────────
    'Fidelity Funds European', 'Fidelity Funds Global', 'Fidelity Funds World',
    'Fidelity Funds Pacific', 'Fidelity Funds Asian', 'Fidelity Funds Bond',
    'Fidelity Funds Emerging', 'Fidelity Funds High Yield', 'Fidelity Funds Income',
    'Fidelity Funds America', 'Fidelity SICAV',

    # ── Franklin Templeton (Luxembourg) ─────────────────────────────────────
    'Franklin European Growth', 'Franklin Global Growth', 'Franklin Technology',
    'Templeton Global Bond', 'Templeton Emerging Markets', 'Franklin Income fund',
    'Franklin Mutual European', 'Franklin Biotechnology', 'Franklin Natural',
    'Templeton Asian Growth', 'Franklin US Opportunities',

    # ── Allianz GI (Luxembourg) ──────────────────────────────────────────────
    'Allianz Interglobal fund', 'Allianz European Equity', 'Allianz Global equity',
    'Allianz Emerging Markets', 'Allianz Technology fund', 'Allianz Income Growth',
    'Allianz Dynamic', 'Allianz Flexi Bond',

    # ── BNP Paribas AM ───────────────────────────────────────────────────────
    'BNP Paribas Funds Europe', 'BNP Paribas Funds Global', 'BNP Paribas Actions',
    'BNP Paribas Bond', 'BNP Paribas Equity', 'BNP Paribas Emerging',
    'BNP Paribas Sustainable', 'BNP Paribas Balanced',

    # ── AXA IM (Luxembourg/France) ───────────────────────────────────────────
    'AXA WF Framlington Europe', 'AXA World Funds Global', 'AXA Valeurs',
    'AXA WF Bond', 'AXA WF Emerging', 'AXA WF Optimal', 'AXA Rosenberg',

    # ── Janus Henderson (Luxembourg) ─────────────────────────────────────────
    'Janus Henderson Horizon Pan European', 'Janus Henderson Horizon Global',
    'Janus Henderson Horizon Technology', 'Janus Henderson European',
    'Janus Henderson Capital', 'Janus Henderson Bond', 'Janus Henderson Income',
    'Janus Henderson Emerging', 'Janus Henderson Balanced',

    # ── Invesco (Luxembourg) ─────────────────────────────────────────────────
    'Invesco Pan European', 'Invesco Global Structured Equity', 'Invesco European',
    'Invesco Emerging Markets', 'Invesco Bond', 'Invesco Balanced fund',
    'Invesco Continental European', 'Invesco Asia',

    # ── JPMorgan AM (Luxembourg) ─────────────────────────────────────────────
    'JPMorgan Funds Global Select', 'JPMorgan Funds America', 'JPMorgan Funds Europe',
    'JPMorgan Funds Emerging', 'JPMorgan Funds Bond', 'JPMorgan Funds Income',
    'JPMorgan Funds Asia', 'JPMorgan Funds Technology', 'JPMorgan Funds Balanced',
    'JPMorgan Funds Multi Asset',

    # ── BlackRock GF (Luxembourg) ────────────────────────────────────────────
    'BlackRock GF World Healthscience', 'BlackRock GF European', 'BlackRock GF Global',
    'BlackRock GF Emerging', 'BlackRock GF Asian', 'BlackRock GF Bond',
    'BlackRock GF Technology', 'BlackRock GF World Gold', 'BlackRock GF Income',
    'BlackRock GF Japan', 'BlackRock GF Continental',

    # ── Goldman Sachs AM (Luxembourg) ────────────────────────────────────────
    'Goldman Sachs Equity Portfolio', 'Goldman Sachs Global equity',
    'Goldman Sachs Emerging Markets', 'Goldman Sachs Bond', 'Goldman Sachs Japan',
    'Goldman Sachs Growth', 'Goldman Sachs Income',

    # ── T. Rowe Price (Luxembourg) ───────────────────────────────────────────
    'T. Rowe Price Global equity', 'T. Rowe Price US Large Cap',
    'T. Rowe Price European', 'T. Rowe Price Emerging', 'T. Rowe Price Dynamic',
    'T. Rowe Price Asian',

    # ── HSBC GIF (Luxembourg) ────────────────────────────────────────────────
    'HSBC GIF Asia equity', 'HSBC GIF Global equity', 'HSBC GIF European',
    'HSBC GIF Emerging', 'HSBC GIF Bond',

    # ── Flossbach von Storch (Luxembourg) ────────────────────────────────────
    'Flossbach von Storch Multiple Opportunities', 'Flossbach SICAV Bond',
    'Flossbach SICAV equity', 'Flossbach von Storch Global',

    # ── Threadneedle / Columbia (Luxembourg) ─────────────────────────────────
    'Threadneedle European equity', 'Threadneedle Global equity',
    'Threadneedle American equity', 'Columbia Threadneedle European',
    'Columbia Threadneedle Global', 'Threadneedle UK',

    # ── Baillie Gifford (Ireland) ─────────────────────────────────────────────
    'Baillie Gifford Long Term Global', 'Baillie Gifford World equity',
    'Baillie Gifford European', 'Baillie Gifford Japanese',

    # ── abrdn / Aberdeen (Luxembourg) ────────────────────────────────────────
    'abrdn Global Equity fund', 'abrdn European Equity', 'abrdn Emerging Markets',
    'Aberdeen Standard European', 'Aberdeen Standard Global', 'abrdn SICAV',
    'abrdn Bond fund',

    # ── M&G (UK) ─────────────────────────────────────────────────────────────
    'M&G Global fund', 'M&G European fund', 'M&G Recovery fund',
    'M&G Optimal Income', 'M&G Bond fund', 'M&G Global Dividend',
    'M&G Dynamic Allocation', 'M&G Episode',

    # ── Candriam (Luxembourg/Belgium) ────────────────────────────────────────
    'Candriam Equities global', 'Candriam Bonds euro', 'Candriam Sustainable',
    'Candriam Multi-Asset', 'Candriam Absolute Return', 'Candriam Index',

    # ── Vontobel (Luxembourg) ────────────────────────────────────────────────
    'Vontobel Fund Equity', 'Vontobel Fund Bond', 'Vontobel Quality Growth',
    'Vontobel Emerging Markets', 'Vontobel Global equity', 'Vontobel TwentyFour',

    # ── Deka (Germany) ───────────────────────────────────────────────────────
    'Deka Global fund', 'Deka Europe equity', 'Deka Bond fund',
    'Deka Dividende fund', 'DekaFonds', 'Deka Convergence',
    'Deka Multi Asset', 'Deka Nachhaltig',

    # ── Union Investment (Germany) ────────────────────────────────────────────
    'UniGlobal fund', 'UniEuropa fund', 'UniDividendenAss',
    'UniAsia Pacific', 'UniEM Global', 'UniFavorit',
    'UniNordAmerika', 'UniRak fund',

    # ── DJE (Luxembourg) ─────────────────────────────────────────────────────
    'DJE Dividende Substanz', 'DJE Equity', 'DJE Short Term',
    'DJE Alpha Renten', 'DJE Zins Dividende',

    # ── Oddo BHF (France/Luxembourg) ─────────────────────────────────────────
    'Oddo BHF European equity', 'Oddo BHF Emerging equity',
    'Oddo BHF Avenir fund', 'Oddo BHF Polaris', 'Oddo BHF Global',

    # ── DNCA (France/Luxembourg) ─────────────────────────────────────────────
    'DNCA Invest Value Europe', 'DNCA Centifolia', 'DNCA Bond',
    'DNCA Invest equity', 'DNCA Alpha',

    # ── Groupama AM (France) ─────────────────────────────────────────────────
    'Groupama Avenir Euro', 'Groupama Global equity',

    # ── Edmond de Rothschild (Luxembourg/France) ─────────────────────────────
    'EdR Fund Equity Europe', 'EdR Fund Bond', 'Edmond de Rothschild Europe',
    'Edmond de Rothschild Global', 'EdR SICAV fund',

    # ── Tikehau (France/Luxembourg) ──────────────────────────────────────────
    'Tikehau Capital fund', 'Tikehau Income Cross Asset', 'Tikehau Credit',

    # ── Sycomore AM (France) ─────────────────────────────────────────────────
    'Sycomore European equity', 'Sycomore Selection Responsable',

    # ── Echiquier (France) ───────────────────────────────────────────────────
    'Echiquier Agenor Mid Cap', 'Echiquier World equity', 'LFDE Echiquier',
    'Echiquier Positive Impact',

    # ── Metropole Gestion (France) ────────────────────────────────────────────
    'Metropole SICAV Europe', 'Metropole Valeur',

    # ── Magellan AM (France) ─────────────────────────────────────────────────
    'Magellan fonds emerging', 'Magellan capital growth',

    # ── Moneta AM (France) ───────────────────────────────────────────────────
    'Moneta Multi Caps', 'Moneta Long Short',

    # ── GAM (Luxembourg/Switzerland) ─────────────────────────────────────────
    'GAM Multiband fund', 'GAM Star equity', 'GAM Investments global',
    'GAM Global Diversified', 'GAM Emerging Markets',

    # ── Man GLG (Luxembourg/Ireland) ─────────────────────────────────────────
    'Man GLG European equity', 'Man GLG Global equity', 'Man Funds equity',
    'Man GLG Income', 'Man GLG Japan',

    # ── UBS AM (Luxembourg) ──────────────────────────────────────────────────
    'UBS Equity Fund global', 'UBS Bond Fund euro', 'UBS Global Equity',
    'UBS European equity', 'UBS Emerging Markets', 'UBS China equity',
    'UBS Key Select', 'UBS Balanced',

    # ── Julius Baer / Baer (Luxembourg) ─────────────────────────────────────
    'Julius Baer Multistock equity', 'Julius Baer Multibond',
    'Julius Baer Global equity',

    # ── Lombard Odier (Luxembourg) ────────────────────────────────────────────
    'LO Funds Equity', 'LO Funds Bond', 'Lombard Odier Sustainable',
    'LO Funds Generation',

    # ── Bantleon (Luxembourg) ─────────────────────────────────────────────────
    'Bantleon Dividend Champions', 'Bantleon Global Multi Asset',

    # ── Berenberg (Luxembourg) ────────────────────────────────────────────────
    'Berenberg European equity', 'Berenberg Global equity', 'Berenberg Sustainable',

    # ── Acatis (Germany/Luxembourg) ──────────────────────────────────────────
    'Acatis Equity Value', 'Acatis Global Value', 'Acatis Fair Value',

    # ── Metzler (Germany) ────────────────────────────────────────────────────
    'Metzler European equity', 'Metzler Global equity',

    # ── Warburg (Germany) ────────────────────────────────────────────────────
    'Warburg Value Fund', 'Warburg Global fund',

    # ── Kempen (Netherlands) ─────────────────────────────────────────────────
    'Kempen Global equity', 'Kempen European equity', 'Kempen Oranje',

    # ── NN Investment Partners (Netherlands) ─────────────────────────────────
    'NN European Equity fund', 'NN Global Equity fund', 'NN Bond fund',
    'NN First Class', 'NN Multi Asset',

    # ── Natixis / Ostrum (France/Luxembourg) ─────────────────────────────────
    'Natixis International Funds', 'Ostrum Bond fund', 'Ostrum European equity',
    'Loomis Sayles European fund', 'Harris Associates Oakmark',

    # ── PIMCO (Ireland/Luxembourg) ───────────────────────────────────────────
    'PIMCO GIS Global Bond', 'PIMCO GIS Income fund', 'PIMCO GIS Total Return',
    'PIMCO GIS European', 'PIMCO GIS Dynamic Bond',

    # ── MFS Meridian (Luxembourg) ────────────────────────────────────────────
    'MFS Meridian European Equity', 'MFS Meridian Global equity',
    'MFS Meridian Emerging Markets', 'MFS Meridian Bond',

    # ── Capital Group (Luxembourg) ───────────────────────────────────────────
    'Capital Group European equity', 'Capital Group Global equity',
    'Capital Group World equity', 'Capital Group Bond',

    # ── Wellington (Luxembourg) ───────────────────────────────────────────────
    'Wellington Opportunistic equity', 'Wellington Global Impact',
    'Wellington European equity', 'Wellington Emerging Markets',

    # ── Neuberger Berman (Luxembourg) ────────────────────────────────────────
    'Neuberger Berman European equity', 'Neuberger Berman Global equity',
    'Neuberger Berman Emerging', 'Neuberger Berman Bond',

    # ── KBC (Belgium) ────────────────────────────────────────────────────────
    'KBC Equity fund', 'KBC Multi Interest', 'KBC Select Immo',

    # ── DPAM / Degroof Petercam (Belgium) ────────────────────────────────────
    'DPAM European Equity', 'DPAM Global equity', 'DPAM Bond fund',
    'Degroof Petercam Sustainable',

    # ── Polar Capital (UK/Ireland) ────────────────────────────────────────────
    'Polar Capital Technology fund', 'Polar Capital Global equity',
    'Polar Capital European equity', 'Polar Capital Healthcare',
    'Polar Capital Biotechnology',

    # ── Liontrust (UK/Ireland) ────────────────────────────────────────────────
    'Liontrust European equity', 'Liontrust Global equity', 'Liontrust Sustainable',
    'Liontrust UK equity',

    # ── Jupiter (UK/Ireland/Luxembourg) ──────────────────────────────────────
    'Jupiter European equity', 'Jupiter Global equity', 'Jupiter Asian equity',
    'Jupiter Income fund', 'Jupiter Dynamic Bond', 'Jupiter Ecology',

    # ── Artemis (UK) ─────────────────────────────────────────────────────────
    'Artemis Global equity', 'Artemis European equity', 'Artemis Income fund',
    'Artemis SmartGARP fund',

    # ── Barings (Luxembourg) ─────────────────────────────────────────────────
    'Barings European equity', 'Barings Global equity', 'Barings Emerging',
    'Barings Bond fund', 'Barings Multi Asset',

    # ── Muzinich (Ireland/Luxembourg) ────────────────────────────────────────
    'Muzinich Global Credit', 'Muzinich European Credit',
    'Muzinich Short Duration Bond',

    # ── BlueBay (Luxembourg) ─────────────────────────────────────────────────
    'BlueBay High Yield Bond', 'BlueBay Investment Grade Bond',
    'BlueBay Global Sovereign',

    # ── Lazard AM (Luxembourg) ───────────────────────────────────────────────
    'Lazard European equity', 'Lazard Global equity', 'Lazard Emerging Markets',
    'Lazard Convertible',

    # ── Fundsmith (UK/Ireland) ────────────────────────────────────────────────
    'Fundsmith Equity fund', 'Fundsmith Emerging Equities',

    # ── Lindsell Train (UK/Ireland) ───────────────────────────────────────────
    'Lindsell Train Global equity', 'Lindsell Train UK equity',

    # ── Montanaro (UK) ────────────────────────────────────────────────────────
    'Montanaro European Smaller', 'Montanaro Better World',

    # ── Ethenea (Luxembourg) ─────────────────────────────────────────────────
    'Ethna Aktiv fund', 'Ethna Global Defensiv', 'Ethna Dynamisch',

    # ── Algebris (Luxembourg) ────────────────────────────────────────────────
    'Algebris Financial Credit', 'Algebris Global Financials',

    # ── SEB (Sweden) ─────────────────────────────────────────────────────────
    'SEB European equity', 'SEB Global equity', 'SEB Technology fund',
    'SEB Nordic fund',

    # ── Handelsbanken (Sweden) ────────────────────────────────────────────────
    'Handelsbanken Global equity', 'Handelsbanken Nordic equity',

    # ── Storebrand (Norway) ───────────────────────────────────────────────────
    'Storebrand Global equity', 'Storebrand Sustainable',

    # ── DNB (Norway) ─────────────────────────────────────────────────────────
    'DNB Global equity', 'DNB Technology fund', 'DNB Nordic equity',

    # ── Evli (Finland) ───────────────────────────────────────────────────────
    'Evli Global equity', 'Evli Nordic equity', 'Evli Bond fund',

    # ── Credit Suisse AM (Luxembourg) ────────────────────────────────────────
    'CS Equity Fund global', 'Credit Suisse Bond fund',

    # ── Standard Life (UK/Luxembourg) ────────────────────────────────────────
    'Standard Life European equity', 'Standard Life Global equity',

    # ── Royal London AM (UK) ─────────────────────────────────────────────────
    'Royal London Global equity', 'Royal London Bond fund',

    # ── Rathbone (UK) ────────────────────────────────────────────────────────
    'Rathbone Global equity', 'Rathbone Income fund',

    # ── Sanso Investment Solutions (France) ──────────────────────────────────
    'Sanso Objectif equity',

    # ── Inocap (France) ──────────────────────────────────────────────────────
    'Inocap Gestion equity',

    # ── Palatine AM (France) ─────────────────────────────────────────────────
    'Palatine Europe Sustainable',

    # ── Covea Finance (France) ────────────────────────────────────────────────
    'Covea Actions equity',

    # ── Triodos (Netherlands) ────────────────────────────────────────────────
    'Triodos Global Equities',

    # ── Generali Investments (Luxembourg) ────────────────────────────────────
    'Generali Investments European', 'Generali Investments Global',

    # ── Eurizon (Italy/Luxembourg) ────────────────────────────────────────────
    'Eurizon Global equity', 'Eurizon Bond fund', 'Eurizon Flexible',
    'Eurizon Sustainable',

    # ── Mediobanca (Italy) ────────────────────────────────────────────────────
    'Mediobanca Banca Mediolanum',

    # ── Anima (Italy/Luxembourg) ─────────────────────────────────────────────
    'Anima Global equity', 'Anima Bond fund', 'Anima Multiasset',

    # ── Tendercapital (Luxembourg) ───────────────────────────────────────────
    'Tendercapital equity',

    # ── Azimut (Italy/Luxembourg) ────────────────────────────────────────────
    'Azimut Global equity', 'Azimut Dynamic fund',

    # ── Mapfre (Spain/Luxembourg) ────────────────────────────────────────────
    'Mapfre Fondos equity',

    # ── Santander AM (Spain/Luxembourg) ──────────────────────────────────────
    'Santander Investment equity',

    # ── BBVA AM (Spain) ───────────────────────────────────────────────────────
    'BBVA Equity fund',

    # ── Bestinver (Spain) ─────────────────────────────────────────────────────
    'Bestinver International fund',

    # ── Magallanes (Spain) ────────────────────────────────────────────────────
    'Magallanes European Equity',

    # ── Cobas AM (Spain) ─────────────────────────────────────────────────────
    'Cobas International equity',

    # ── Alken AM (Luxembourg) ────────────────────────────────────────────────
    'Alken European Opportunities', 'Alken Absolute Return',

    # ── Argonaut (UK/Luxembourg) ─────────────────────────────────────────────
    'Argonaut European Income',

    # ── Indus Capital (Luxembourg) ───────────────────────────────────────────
    'Indus Japan fund',

    # ── NN Group / Nationale Nederlanden ─────────────────────────────────────
    'Nationale Nederlanden equity',

    # ── Raiffeisen (Austria) ──────────────────────────────────────────────────
    'Raiffeisen Nachhaltigkeit equity', 'Raiffeisen Global equity',

    # ── Erste AM (Austria) ────────────────────────────────────────────────────
    'Erste Responsible equity', 'Erste Bond fund',

    # ── Spängler (Austria) ────────────────────────────────────────────────────
    'Spängler IQAM equity',

    # ── Kepler (Austria) ─────────────────────────────────────────────────────
    'Kepler Global equity',

    # ── Swisscanto (Switzerland) ─────────────────────────────────────────────
    'Swisscanto Equity fund', 'Swisscanto Bond fund', 'Swisscanto Sustainable',

    # ── Bellevue (Switzerland) ────────────────────────────────────────────────
    'Bellevue Healthcare fund', 'Bellevue Medtech', 'Bellevue Entrepreneur',

    # ── Zürcher Kantonalbank (Switzerland) ────────────────────────────────────
    'ZKB Equity fund',

    # ── Searchterm categoriali generici ──────────────────────────────────────
    'europe equity SICAV fund', 'global equity SICAV fund',
    'bond europe SICAV fund', 'mixed allocation SICAV',
    'UCITS equity fund europe', 'UCITS bond fund europe',
    'SICAV global equity EUR', 'FCP actions europe growth',
    'europe growth equity UCITS', 'europe value equity UCITS',
    'sustainable SICAV europe equity', 'ESG fund europe SICAV',
    'infrastructure SICAV europe', 'real estate SICAV europe',
    'convertible bonds SICAV EUR', 'high yield bond SICAV europe',
    'emerging markets SICAV EUR', 'small cap europe SICAV',
    'dividend fund europe SICAV', 'balanced fund europe SICAV',
    'technology fund europe UCITS', 'healthcare SICAV europe',
    'flexible allocation SICAV EUR', 'absolute return SICAV EUR',
    'global bond fund SICAV', 'credit bond SICAV EUR',
    'multi asset SICAV europe', 'capital protection SICAV',

    # ── Per area geografica ────────────────────────────────────────────────────
    'equity germany SICAV', 'equity france SICAV', 'equity italy SICAV',
    'equity spain SICAV', 'equity switzerland SICAV',
    'nordic equity UCITS', 'benelux equity fund',
    'UK equity UCITS fund', 'european bond SICAV EUR',
    'asia equity UCITS fund', 'japan equity SICAV EUR',
    'china equity SICAV', 'india equity UCITS',

    # ── Stili/strategie ────────────────────────────────────────────────────────
    'value investing europe fund', 'growth equity europe fund',
    'momentum equity SICAV', 'quality equity europe fund',
    'dividend growth europe fund', 'low volatility europe UCITS',
    'long short equity europe', 'market neutral SICAV',
    'global macro SICAV', 'event driven SICAV',
]


def _is_eu_fund(symbol):
    """True se il ticker ha un suffisso di borsa europea."""
    for sfx in EU_SUFFIXES:
        if symbol.endswith(sfx):
            return True
    return False


def _yf_search_isin(isin, retries=3):
    """Cerca un ISIN su Yahoo Finance Search API. Restituisce (ticker, nome)."""
    url = (
        f"https://query2.finance.yahoo.com/v1/finance/search"
        f"?q={isin}&quotesCount=5&newsCount=0&listsCount=0"
        f"&enableFuzzyQuery=false&enableCb=false"
    )
    return _yf_search_raw(url, prefer_types=('MUTUALFUND', 'ETF'), retries=retries, mode='first')


def _yf_search_terms(term, retries=3):
    """
    Cerca un termine libero su Yahoo Finance.
    Restituisce lista di (ticker, nome) per i fondi EU trovati.
    """
    encoded = urllib.parse.quote(term)
    url = (
        f"https://query2.finance.yahoo.com/v1/finance/search"
        f"?q={encoded}&quotesCount=8&newsCount=0&listsCount=0"
        f"&enableFuzzyQuery=false&enableCb=false"
    )
    return _yf_search_raw(url, prefer_types=('MUTUALFUND',), retries=retries, mode='all_eu')


def _yf_search_raw(url, prefer_types, retries, mode):
    """
    Chiamata HTTP comune per entrambe le funzioni di ricerca.
    mode='first'  → restituisce (ticker, nome) del primo risultato trovato
    mode='all_eu' → restituisce lista [(ticker, nome)] di tutti i fondi EU
    """
    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/124.0.0.0 Safari/537.36'),
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode('utf-8'))
            quotes = data.get('quotes', [])

            if mode == 'first':
                # Preferisce MUTUALFUND, poi ETF, poi qualsiasi
                for qtype in prefer_types + (None,):
                    for q in quotes:
                        if qtype is None or q.get('quoteType') == qtype:
                            sym = q.get('symbol', '')
                            if sym:
                                return sym, q.get('shortname') or q.get('longname') or ''
                return None, None

            else:  # mode == 'all_eu'
                results = []
                seen = set()
                for q in quotes:
                    if q.get('quoteType') not in prefer_types:
                        continue
                    sym = q.get('symbol', '')
                    if not sym or sym in seen:
                        continue
                    if _is_eu_fund(sym):
                        seen.add(sym)
                        results.append((sym, q.get('shortname') or q.get('longname') or ''))
                return results

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * attempt
                print(f"    [429] Rate limit — attendo {wait}s...", flush=True)
                time.sleep(wait)
            else:
                return (None, None) if mode == 'first' else []
        except Exception:
            if attempt < retries:
                time.sleep(random.uniform(3, 6))
            else:
                return (None, None) if mode == 'first' else []

    return (None, None) if mode == 'first' else []


def _yf_get_info(ticker, retries=3):
    """Recupera metadati fondo via yfinance: TER, categoria, gestore, AUM, MS rating."""
    if not _YF_OK:
        return {}
    for attempt in range(1, retries + 1):
        try:
            fund = yf.Ticker(ticker)
            info = fund.info

            ter = info.get('annualReportExpenseRatio',
                  info.get('netExpenseRatio',
                  info.get('totalExpenseRatio')))

            # Fallback TER via funds_data
            if ter is None:
                try:
                    fd = fund.funds_data
                    if fd and fd.fund_operations is not None:
                        ops = fd.fund_operations
                        for field in ['Annual Report Expense Ratio', 'Net Expense Ratio', 'Expense Ratio']:
                            if field in ops.index:
                                val = ops.loc[field].iloc[0]
                                if val is not None and str(val) not in ('<NA>', 'nan', 'None'):
                                    ter = float(val)
                                    break
                except Exception:
                    pass

            category = info.get('category') or ''
            if not category:
                try:
                    fd = fund.funds_data
                    if fd and fd.fund_overview is not None:
                        ov = fd.fund_overview
                        for field in ['Category', 'Fund Category', 'Morningstar Category']:
                            if field in ov.index:
                                val = str(ov.loc[field].iloc[0])
                                if val not in ('nan', 'N/A', 'None', ''):
                                    category = val
                                    break
                except Exception:
                    pass

            return {
                'name':       info.get('longName') or info.get('shortName') or '',
                'ter':        ter,
                'category':   category or info.get('fundFamily') or '',
                'manager':    info.get('fundFamily') or '',
                'currency':   info.get('currency') or 'EUR',
                'aum':        info.get('totalAssets') or info.get('netAssets') or 0,
                'ms_rating':  info.get('morningStarOverallRating') or info.get('morningStarRiskRating'),
                'quote_type': info.get('quoteType') or '',
            }
        except Exception:
            if attempt < retries:
                time.sleep(random.uniform(3, 6))
    return {}


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


def _known_tickers(cache):
    """Set di tutti i yahoo_ticker gia' in cache (evita duplicati in fase 2)."""
    return {v['yahoo_ticker'] for v in cache.values() if v.get('yahoo_ticker')}


def run_phase1_isin(cache, update_only=False):
    """
    FASE 1: cerca ogni ISIN seed su Yahoo Finance.
    Salta gli ISIN gia' in cache (se update_only=False, rielabora tutto).
    """
    isins = list(EU_SEED_ISINS)
    if update_only:
        isins = [i for i in isins
                 if i not in cache or cache[i].get('error') or not cache[i].get('yahoo_ticker')]

    total  = len(isins)
    found  = 0
    errors = 0
    print(f"\nFASE 1 — ISIN seed: {total} da processare", flush=True)
    print('-' * 60, flush=True)

    for idx, isin in enumerate(isins, 1):
        print(f"  [{idx:>3}/{total}] {isin} ...", end=' ', flush=True)

        ticker, yf_name = _yf_search_isin(isin)
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        if not ticker:
            errors += 1
            cache[isin] = {
                'isin': isin, 'source': 'isin_seed',
                'error': 'ticker non trovato su Yahoo Finance',
                'fetched_at': datetime.now().strftime('%Y-%m-%d'),
            }
            print("non trovato", flush=True)
        else:
            meta  = _yf_get_info(ticker)
            name  = meta.get('name') or yf_name or ''
            ter_s = f"{meta['ter']*100:.2f}%" if meta.get('ter') else '-'
            print(f"OK  {ticker:<22} TER:{ter_s:<7} {name[:30]}", flush=True)
            found += 1
            cache[isin] = {
                'isin':         isin,
                'source':       'isin_seed',
                'yahoo_ticker': ticker,
                'name':         name,
                'ter':          meta.get('ter'),
                'category':     meta.get('category', ''),
                'manager':      meta.get('manager', ''),
                'currency':     meta.get('currency', 'EUR'),
                'aum':          meta.get('aum', 0),
                'ms_rating':    meta.get('ms_rating'),
                'quote_type':   meta.get('quote_type', ''),
                'fetched_at':   datetime.now().strftime('%Y-%m-%d'),
            }
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        if idx % BATCH_SIZE == 0:
            save_cache(cache)
            print(f"  >>> Checkpoint cache ({idx}/{total}) — trovati:{found} errori:{errors}", flush=True)

    save_cache(cache)
    print(f"\nFASE 1 completata: trovati {found}/{total}", flush=True)
    return found, errors


def run_phase2_discover(cache):
    """
    FASE 2: scansiona Yahoo Finance con ~420 termini di ricerca.
    Per ogni termine raccoglie tutti i fondi con suffisso borsa EU.
    Salta i ticker gia' in cache.
    Poi chiama yfinance per i metadati dei nuovi ticker trovati.
    """
    terms  = list(DISCOVERY_TERMS)
    total  = len(terms)
    known  = _known_tickers(cache)
    new_tickers = {}  # ticker -> nome grezzo (da arricchire dopo)

    print(f"\nFASE 2 — Discovery termini: {total} termini da cercare", flush=True)
    print('-' * 60, flush=True)

    for idx, term in enumerate(terms, 1):
        results = _yf_search_terms(term)
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        new_here = 0
        for sym, name in results:
            if sym not in known and sym not in new_tickers:
                new_tickers[sym] = name
                new_here += 1

        if idx % 50 == 0 or new_here > 0:
            print(f"  [{idx:>3}/{total}] '{term[:40]}' → "
                  f"+{new_here} nuovi (totale nuovi: {len(new_tickers)})", flush=True)

    print(f"\nFASE 2 ricerca completata: {len(new_tickers)} nuovi ticker EU da arricchire", flush=True)
    print('-' * 60, flush=True)

    # Arricchisci i nuovi ticker con yfinance
    enriched = 0
    ticker_list = list(new_tickers.items())
    for idx, (ticker, yf_name) in enumerate(ticker_list, 1):
        print(f"  [{idx:>4}/{len(ticker_list)}] {ticker:<24} ...", end=' ', flush=True)
        meta  = _yf_get_info(ticker)
        name  = meta.get('name') or yf_name or ''
        ter_s = f"{meta['ter']*100:.2f}%" if meta.get('ter') else '-'
        print(f"TER:{ter_s:<7} {name[:30]}", flush=True)
        enriched += 1

        # Chiave cache: il ticker stesso (non abbiamo ISIN)
        cache[ticker] = {
            'source':       'discovery',
            'yahoo_ticker': ticker,
            'name':         name,
            'ter':          meta.get('ter'),
            'category':     meta.get('category', ''),
            'manager':      meta.get('manager', ''),
            'currency':     meta.get('currency', 'EUR'),
            'aum':          meta.get('aum', 0),
            'ms_rating':    meta.get('ms_rating'),
            'quote_type':   meta.get('quote_type', ''),
            'fetched_at':   datetime.now().strftime('%Y-%m-%d'),
        }

        if idx % BATCH_SIZE == 0:
            save_cache(cache)
            print(f"  >>> Checkpoint cache ({idx}/{len(ticker_list)})", flush=True)

        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

    save_cache(cache)
    print(f"\nFASE 2 completata: {enriched} fondi EU aggiunti", flush=True)
    return enriched


def print_stats(cache):
    total      = len(cache)
    from_isin  = sum(1 for v in cache.values() if v.get('source') == 'isin_seed')
    from_disc  = sum(1 for v in cache.values() if v.get('source') == 'discovery')
    errors     = sum(1 for v in cache.values() if v.get('error'))
    has_ticker = sum(1 for v in cache.values() if v.get('yahoo_ticker') and not v.get('error'))
    has_ter    = sum(1 for v in cache.values() if v.get('ter') is not None and not v.get('error'))
    has_ms     = sum(1 for v in cache.values() if v.get('ms_rating') and not v.get('error'))
    ready      = sum(1 for v in cache.values()
                     if v.get('yahoo_ticker') and v.get('ter') is not None and not v.get('error'))

    print(f"\n{'='*60}")
    print(f"  FONDI EU UNIVERSE — STATISTICHE CACHE")
    print(f"{'='*60}")
    print(f"  Voci totali in cache:                      {total:>6}")
    print(f"  Da ISIN seed (fase 1):                     {from_isin:>6}")
    print(f"  Da discovery termini (fase 2):             {from_disc:>6}")
    print(f"  Errori (ISIN non trovato):                 {errors:>6}")
    print(f"  Con ticker Yahoo Finance:                  {has_ticker:>6}")
    print(f"  Con TER disponibile:                       {has_ter:>6}")
    print(f"  Con Morningstar rating:                    {has_ms:>6}")
    print(f"  PRONTI per lo screener (ticker + TER):     {ready:>6}")
    print(f"{'='*60}\n")

    if has_ticker > 0:
        print("Campione fondi trovati (primi 30):")
        shown = 0
        for key, v in cache.items():
            if v.get('yahoo_ticker') and not v.get('error'):
                ter_s = f"{v['ter']*100:.2f}%" if v.get('ter') else '-'
                src   = 'ISIN' if v.get('source') == 'isin_seed' else 'DISC'
                print(f"  [{src}] {v['yahoo_ticker']:<24} TER:{ter_s:<7} {v.get('name','')[:35]}")
                shown += 1
                if shown >= 30:
                    print(f"  ... e altri {has_ticker - 30} fondi")
                    break


def main():
    mode_isin     = '--isin'     in sys.argv
    mode_discover = '--discover' in sys.argv
    mode_update   = '--update'   in sys.argv
    mode_stats    = '--stats'    in sys.argv

    cache = load_cache()

    if mode_stats:
        print_stats(cache)
        return

    # Default: entrambe le fasi
    run_p1 = mode_isin or mode_update or (not mode_isin and not mode_discover)
    run_p2 = mode_discover or (not mode_isin and not mode_discover)

    if run_p1:
        run_phase1_isin(cache, update_only=mode_update)

    if run_p2:
        run_phase2_discover(cache)

    print_stats(cache)


if __name__ == '__main__':
    main()
