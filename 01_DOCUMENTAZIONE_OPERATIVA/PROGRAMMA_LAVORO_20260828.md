# PROGRAMMA DI LAVORO — RT2026 / FVC
**Aggiornato:** 2026-08-28 | **Lancio:** 1 settembre 2026

---

## 🔴 URGENTE — entro 1 settembre (4 giorni)

| # | Task | Chi | Note |
|---|---|---|---|
| 1 | **WhatsApp verifica SMS** +34 680 67 87 34 | Luciano | Rate limit Meta scaduto — ritentare oggi/domani da Business Manager |
| 2 | **Facebook Page Token** rinnovare | Elisabetta Iori | developers.facebook.com → app 841836765343945 → genera token 60gg → manda il token a Luciano |
| 3 | **Instagram** | dipende da #2 | Si sblocca automaticamente dopo token Facebook |
| 4 | **Task Scheduler sync fatture** | Luciano | Eseguire `installa_sync_fatture.bat` come Amministratore — UNA VOLTA SOLA |

---

## 🔴 TECNICO — Output PDF report cliente

| # | Task | Dettaglio |
|---|---|---|
| 7 | **Fix PDF report + area cliente** | Layout/colonne non conformi alle indicazioni originali + PDF non caricato nell'area riservata per ordine bancario/piattaforma — da specificare nel dettaglio |

---

## 🟡 SESSIONE PROSSIMA — Social Media

| # | Task | Dettaglio |
|---|---|---|
| 5 | **Facebook/Instagram publish** | Collegare publish_to_all_channels() dopo token Facebook rinnovato |
| 6 | **Test post campagna** | Verificare che il 1° settembre alle 10:00 UTC il post LinkedIn (profilo Luciano) + Facebook parta correttamente |

---

## 🟢 DOPO IL LANCIO

| # | Task |
|---|---|
| 8 | Social calendar FR/DE (primo post FR: 2027-01-02) |
| 9 | Brevo webhook su wealth.fuerteventurecapital.com |
| 10 | WhatsApp template screener_pronto — attendere approvazione Meta |

---

## ✅ COMPLETATO SESSIONE 2026-08-28 (notte)

| Task | Stato |
|---|---|
| **report_pdf.py — PDF landscape A4** (297×210mm, 273mm usabili) | ✅ |
| **Colonne AZIONI** — 19 colonne unificata BASIC/PRO/VALUE: Ticker,Nome,Val,Mercato,Indice,Prezzo,Var1D%,Score,1M%,3M%,6M%,YTD%,1A%,P/B,ROE,EV/FCF,ND/EBITDA,MktCap,Settore | ✅ |
| **FREQ → %** — `pct=round(cnt/total_days*100)`, verde≥50%, oro≥25% | ✅ |
| **ticker_frequency.py** — aggiunto `_meta.total_days` per calcolo FREQ% | ✅ |
| **Pagina 1 = Legenda** — Score + 12 indicatori/colonne; esclusi pesi e fogli Excel | ✅ |
| **Pagina 2 eliminata** — Scheda Ordine Bancario rimossa | ✅ |
| **Logo FVC da assets.py** — `FUERTE_LOGO_B64` (512×512 quadrato); header 44mm per ospitarlo | ✅ |
| **dashboard.py** — `report_row()` PDF-first (controlla PDF prima di Excel) | ✅ |
| Deploy VPS + restart rt2026.service | ✅ |

## ✅ COMPLETATO SESSIONE 2026-08-28 (sera)

| Task | Stato |
|---|---|
| Fattura PDF — fix layout: logo 54mm spostato (separator y=72, FORNITORE y=76, table min 126) | ✅ |
| Fattura PDF — "MODALITÀ" con accento corretto | ✅ |
| Fattura manuale — modal dashboard + POST /api/fatture/manuale + genera_fattura_manuale_pdf() | ✅ |
| Reset contatore fatture — POST /api/fatture/reset-contatore (azzera + cancella PDF) | ✅ |
| Deploy su VPS — dashboard.py + html_admin.py via SCP + riavvio | ✅ |
| CRM & MARKETING B2C — parametrizzazione completa (config.json, .env.example, TEMPLATE KB) | ✅ |
| ISTRUZIONI_USO.md — sezione QUICK START in cima al file | ✅ |

## ✅ COMPLETATO SESSIONE 2026-08-28 (pomeriggio)

| Task | Stato |
|---|---|
| CampagnaAgent — KB 4 strati, segmentazione, A/B test Claude | ✅ |
| Knowledge Base compilata con programma CRM & Marketing completo | ✅ |
| Canale bidirezionale Agente ↔ Luciano (inbox + email alert) | ✅ |
| Documentazione salvata in tutti i posti (memoria/GitHub/cartelle) | ✅ |
| CRM & MARKETING B2C aggiornato con agente e documentazione | ✅ |

---

## ✅ COMPLETATO SESSIONE 2026-08-27/28

| Task | Stato |
|---|---|
| Email campagna automatica 250/giorno alle 09:00 UTC — daemon live sul VPS | ✅ |
| Social post automatico LinkedIn+Facebook alle 10:00 UTC (60min dopo email) | ✅ |
| Calendario 4 mesi Set-Dic 2026 — 30.500 email pianificate | ✅ |
| Selettore 5 lingue nell'email (IT/ES/EN/FR/DE) | ✅ |
| Landing page legge ?lang=XX e si traduce automaticamente | ✅ |
| Immagine WealthOS (logo W) nelle email ottobre e dicembre | ✅ |
| Sync fatture VPS → Desktop ogni ora (sync_fatture_vps.ps1) | ✅ |
| Template CRM B2C salvato in Desktop\CRM & MARKETING B2C\ | ✅ |
| Fatture VPS 0027/0028/0030/0032 sincronizzate in locale | ✅ |

---

## STATO CANALI SOCIAL (2026-08-28)

| Canale | Stato | Azione |
|---|---|---|
| Brevo Email | ✅ LIVE | Nessuna |
| LinkedIn | ✅ LIVE (profilo Luciano) | Company page: impossibile via API (LinkedIn policy) |
| Facebook | ❌ Token scaduto (errore 190/492) | Elisabetta → rinnova token |
| Instagram | ⏳ Dipende da Facebook | — |
| WhatsApp | ⚠️ DISCONNECTED | Verifica SMS da ritentare |

---

## SEQUENZA AUTOMATICA DAL 1 SETTEMBRE

```
09:00 UTC  →  250 email SALARY TRAP (IT) ai prospect
10:00 UTC  →  Post LinkedIn + Facebook (stesso tema)
```
Nessuna azione richiesta — daemon già attivo sul VPS.

---

## FILE CHIAVE

| File | Percorso |
|---|---|
| Script sync fatture | Desktop\Robot Trader 2026\sync_fatture_vps.ps1 |
| Installa Task Scheduler | Desktop\Robot Trader 2026\installa_sync_fatture.bat |
| Calendario campagna email | /root/rt2026/campagna_email_calendar.json (VPS) |
| Tracker invii mensile | /root/rt2026/campagna_invii_tracker.json (VPS) |
| Social calendar | /root/rt2026/social_calendar.json (VPS) — 231 post |
| Template CRM B2C | Desktop\CRM & MARKETING B2C\ |
