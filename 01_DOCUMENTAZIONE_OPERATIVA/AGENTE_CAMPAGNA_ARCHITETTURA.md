# AGENTE CAMPAGNA — ARCHITETTURA COMPLETA
**Versione:** 1.0 | **Data:** 2026-08-28 | **Stato:** IN SVILUPPO

---

## VISIONE

Trasformare l'automazione email/social da **timer con template fissi** a **agente intelligente** che impara, adatta e scala all'umano nei momenti giusti.

---

## ATTORI DEL SISTEMA

| Attore | Ruolo |
|---|---|
| **Agente** | Decide, analizza, impara, propone |
| **Luciano** | Approva, supervisiona, interviene |
| **Prospect** | Reagisce — apre, clicca, disdice, ignora |
| **Brevo** | Delivery + fonte dati comportamentali |
| **LinkedIn / Facebook** | Canale social + engagement |
| **Claude API** | Generazione contenuto + evoluzione template |
| **Alpha Vantage** | Contesto mercato (VIX, trend indici) |

---

## LOOP GIORNALIERO

```
08:45  ANALISI
       ├─ Legge Brevo stats ieri (open/click/unsub)
       ├─ Identifica opener e clicker (Brevo events API)
       ├─ Aggiorna stato prospect nel DB
       ├─ Aggiorna KB empirical con dati freschi
       ├─ Legge contesto mercato (Alpha Vantage)
       └─ Valuta escalation a Luciano

08:50  DECISIONE  [log reasoning salvato]
       ├─ Sceglie soggetto (KB subject_stats + test A/B)
       ├─ Assegna lingua per prospect (da paese)
       └─ Assegna variante contenuto per segmento

09:00  ESECUZIONE
       └─ 250 email segmentate

10:00  SOCIAL
       └─ Post LinkedIn + Facebook
```

---

## 4 STRATI KNOWLEDGE BASE

### Strato 1 — STRATEGIC (controllo umano)
```json
{
  "priorita_temi": ["SALARY_TRAP", "WEALTHOS_PROMO"],
  "mercati_target": ["IT", "ES", "EN"],
  "obiettivi": "Conversioni RT2026 + WealthOS Q4 2026",
  "soglie": {
    "open_rate_minimo": 0.15,
    "click_rate_minimo": 0.02,
    "unsub_allarme_giornaliero": 10,
    "giorni_sotto_soglia_pausa": 3
  }
}
```
**Regola:** l'agente legge, non scrive. Modificabile solo da Luciano.

### Strato 2 — EMPIRICAL (agente aggiorna ogni 08:45)
- Open/click rate per tema, lingua, giorno settimana, segmento
- Subject line performance con sample size
- Segment preferences (PAIN_HOOK vs CTA vs SOCIAL_PROOF per segmento)

### Strato 3 — MARKET CONTEXT (Alpha Vantage ogni mattina)
- Trend mercati (su/giù/neutro)
- VIX level → mercato volatile = SALARY_TRAP più efficace
- Tema suggerito dal contesto → agente può proporre override calendario

### Strato 4 — CONTENT EVOLUTION (loop Claude → test → apprendimento)
- Soggetti generati da Claude basati su vincitori storici
- A/B test in corso (varianti vs controllo)
- Risultati test → vincitore diventa standard
- Ciclo riparte ogni settimana

---

## SEGMENTI PROSPECT

| Segmento | Comportamento | Contenuto | Azione |
|---|---|---|---|
| **new** | Mai contattato | PAIN_HOOK — awareness forte | Invio standard |
| **opener** | Aperto, non cliccato | SOLUTION + CTA diretta | Re-targeting |
| **clicker** | Ha cliccato link | — | **PASSA A LUCIANO** |
| **cold** | 3+ email ignorate | SOCIAL_PROOF — re-engagement | Ultimo tentativo |
| **unsub** | Disiscritto | — | Rimosso permanentemente |

---

## ESCALATION A LUCIANO

| Trigger | Azione Agente |
|---|---|
| Open rate < 15% per 3 giorni | PAUSA + ALERT CRITICO dashboard |
| Unsub > 10 in un giorno | PAUSA IMMEDIATA + alert |
| Prospect clicca | Notifica personale → tocca a Luciano |
| Proposta cambio calendario mese | Scrive suggestion → RICHIEDE APPROVAZIONE |
| Token Brevo/LinkedIn/Facebook scaduto | ALERT tecnico |
| Tema sotto soglia 3 settimane | Proposta sostituzione → aspetta OK |
| Pattern anomalo rilevato | Segnalazione advisory |

**Regola fondamentale:** l'agente non tocca mai il calendario del mese successivo senza approvazione umana.

---

## EVOLUTION LOOP CONTENUTI

```
1. Analizza subject_stats (sample > 100)
2. Identifica top 3 e bottom 3 soggetti
3. Chiede a Claude: "Genera 5 nuovi soggetti basati su questi vincitori"
4. Inserisce varianti in content_variants → stato: "da_testare"
5. Nei 10 invii successivi ruota tra varianti (A/B)
6. Vincitore → stato: "standard"
7. Ciclo ricomincia la settimana dopo
```

---

## FILE SISTEMA

| File | Ruolo |
|---|---|
| `campagna_agent.py` | Cervello — classe CampagnaAgent |
| `campagna_knowledge.json` | KB 4 strati |
| `campagna_kpi.json` | Log KPI giornaliero |
| `campagna_suggestions.json` | Proposte in attesa approvazione Luciano |
| `campagna_email_calendar.json` | Calendario (punto di partenza, non fonte di verità) |

---

## DASHBOARD — WIDGET AGENTE

| Widget | Contenuto |
|---|---|
| **Stato Agente** | Running / Paused / Alert + ultimo reasoning |
| **KPI Live** | Open rate, click rate, trend 7gg, vs mese prec. |
| **Funnel Prospect** | new → opener → clicker → da contattare |
| **Log Decisioni** | Perché ha scelto quel soggetto/variante oggi |
| **Inbox Suggerimenti** | Proposte → Luciano approva/rifiuta |
| **Alert Center** | Escalation in attesa di intervento |
| **Knowledge Base** | Cosa ha imparato — top soggetti, insight, pattern |

---

## STATO IMPLEMENTAZIONE

- [x] Architettura definita e approvata
- [ ] campagna_knowledge.json — struttura iniziale
- [ ] campagna_agent.py — classe CampagnaAgent
- [ ] dashboard.py — integrazione agente in _campagna_batch_daily()
- [ ] html_admin.py — widget dashboard agente
- [ ] Test end-to-end
