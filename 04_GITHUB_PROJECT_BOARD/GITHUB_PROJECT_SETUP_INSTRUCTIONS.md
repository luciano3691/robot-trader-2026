# 🚀 GITHUB PROJECT BOARD SETUP
## Come creare il board ROBOT TRADER - Maggio 2026 Development

---

## STEP 1: Accedi a GitHub

```
https://github.com/newcapitalfuerte-ally/robot-trader
```

Username: newcapitalfuerte-ally
Password: (your password)

---

## STEP 2: Crea il Project Board

### Via Web Interface:

1. **Apri il repository**
   ```
   https://github.com/newcapitalfuerte-ally/robot-trader
   ```

2. **Clicca su "Projects" tab** (in alto, tra "Settings" e "Security")

3. **Clicca "New project"**
   - Name: `ROBOT TRADER - Maggio 2026 Development`
   - Description: `Maggio 2026 sprint: FONDI + ETF modules (21 issues, 4 weeks)`
   - Template: `Table` (or Kanban - your choice)
   - Visibility: `Public`

4. **Clicca "Create project"**

---

## STEP 3: Configura le colonne

Se hai scelto **Table** view:

Default fields:
- Title
- Status (Backlog, In Progress, In Review, Done)
- Priority (P0, P1)
- Assignee
- Milestone
- Week

Se preferisci **Kanban** view:

Crea 4 colonne:
1. **Backlog** - Not started
2. **In Progress** - Currently working
3. **In Review** - Code review/testing
4. **Done** - Completed

---

## STEP 4: Crea le 21 Issues

### Metodo A: Via Web UI (manuale, 10 minuti)

1. **Clicca "+ New issue"**
2. **Compila i campi:**
   - Title: `[FONDI] Setup module structure & database schema` (from issue #1)
   - Description: (copia dalla sezione DESCRIPTION nel documento)
   - Labels: `fondi`, `priority:p0`, `week:1`
   - Assignee: `luciano.manicardi@lineexpress.it` (you)
   - Milestone: Create new → `May 7, 2026` (Week 1)
   - Estimated: (aggiungi nei commenti)

3. **Clicca "Create issue"**

4. **Ripeti per tutti i 21 issues** (tedious but straightforward)

---

### Metodo B: Via GitHub API (automatico, script Python)

Creerò uno script Python che popola tutte le 21 issues automaticamente!

**Prerequisiti:**
- GitHub Personal Access Token (PAT)
- Python 3.8+
- PyGithub library

---

## STEP 5 (Optional): Usa lo Script di Automazione

Ho creato uno script Python che popola AUTOMATICAMENTE:
- 21 Issues
- Labels
- Milestones
- Project Board

**Nome:** `create_github_issues.py`

---

## 📋 ISSUE TEMPLATE

Usa questo template per ogni issue:

```markdown
# [FONDI] Setup module structure & database schema

## Type
Task

## Priority
P0 (Critical)

## Week
Week 1 (May 1-7)

## Assignee
@luciano.manicardi@lineexpress.it

## Estimated Time
8 hours

## Description

### What needs to be done
- Create backend/modules/funds/ directory structure
  - __init__.py
  - models.py (Fund model with TER, Alpha, Sharpe, etc.)
  - screener.py (FundsScreener class)
  - data_fetcher.py (Yahoo Finance integration)
  - tests/test_funds_screener.py

### Database Schema
- Fund ID
- Name / ISIN / Ticker
- TER (%)
- Alpha (%)
- Sharpe Ratio
- Performance YTD (%)
- Volatility (Std Dev %)
- Max Drawdown (%)
- Last updated
- Source (Yahoo Finance)

### FastAPI Updates
- Add /api/funds/screen endpoint (placeholder)
- Add /api/funds/results endpoint (placeholder)
- Add fund tier to /api/pricing

### Acceptance Criteria
- [ ] Directory structure created
- [ ] All models defined + unit tests
- [ ] API endpoints functional
- [ ] Database schema created
- [ ] Tests passing (>85% coverage)

### Dependencies
- None

### Related
- #2 Yahoo Finance FONDI
- #3 Screening Logic FONDI
```

---

## 🎯 PRIORITY LABELS

Create these labels in GitHub:

```
priority:p0    → Red     (Critical)
priority:p1    → Orange  (High)
priority:p2    → Yellow  (Medium)

module:fondi   → Blue    (FONDI module)
module:etf     → Purple  (ETF module)
module:core    → Green   (Core/shared)

week:1         → (Week 1)
week:2         → (Week 2)
week:3         → (Week 3)
week:4         → (Week 4)

type:task      → Task
type:bug       → Bug
type:feature   → Feature
type:docs      → Documentation

status:backlog → Backlog
status:in-progress → In Progress
status:review  → In Review
status:done    → Done
```

---

## 📅 CREATE MILESTONES

GitHub → "Milestones" tab

```
Milestone 1: May 7, 2026
├─ Title: "FONDI Week 1 - Foundation"
├─ Description: "Setup + Data fetcher + Screening + Email + Tests"
└─ Due date: 2026-05-07
   Issues: #1, #2, #3, #4, #5

Milestone 2: May 14, 2026
├─ Title: "FONDI Week 2 - Completion"
├─ Description: "API + Pricing + Scheduler + Caching + Integration tests"
└─ Due date: 2026-05-14
   Issues: #6, #7, #8, #9, #10

Milestone 3: May 21, 2026
├─ Title: "FONDI Prod + ETF Week 1"
├─ Description: "FONDI deployment + ETF foundation"
└─ Due date: 2026-05-21
   Issues: #11, #12, #13, #14, #15

Milestone 4: May 28, 2026
├─ Title: "ETF Complete + All Prod"
├─ Description: "ETF completion + Production deployment"
└─ Due date: 2026-05-28
   Issues: #16, #17, #18, #19, #20, #21
```

---

## 🔧 AUTOMATION SCRIPT (Optional)

Se preferisci creare le issues via Python script:

```python
from github import Github
import json

# GitHub Personal Access Token
TOKEN = "ghp_your_token_here"
REPO = "newcapitalfuerte-ally/robot-trader"

g = Github(TOKEN)
repo = g.get_repo(REPO)

# Issues data (from MAGGIO_PROJECT_BOARD_COMPLETE.md)
issues_data = [
    {
        "title": "[FONDI] Setup module structure & database schema",
        "body": "...",
        "labels": ["priority:p0", "module:fondi", "week:1", "type:task"],
        "milestone": "May 7, 2026",
        "assignee": "luciano"
    },
    # ... 21 issues total
]

# Create each issue
for issue_data in issues_data:
    issue = repo.create_issue(
        title=issue_data["title"],
        body=issue_data["body"],
        labels=issue_data["labels"],
        # milestone=...,  # requires milestone ID
        # assignee=issue_data["assignee"]
    )
    print(f"Created issue: {issue.number} - {issue.title}")
```

---

## ✅ QUICK START - MANUAL OPTION

Se preferisci creare manualmente (più veloce che aspettare):

**Time needed: ~20 minuti**

1. Apri GitHub
2. New Project: `ROBOT TRADER - Maggio 2026 Development`
3. Create 21 issues (copy-paste titles dalla lista sotto)
4. Aggiungi labels/milestones dopo

---

## 📋 QUICK ISSUE LIST (copy-paste titles)

### WEEK 1 (5 issues)
1. [FONDI] Setup module structure & database schema
2. [FONDI] Implement Yahoo Finance data fetcher for funds
3. [FONDI] Implement funds screening filters
4. [FONDI] Email notifier integration for funds results
5. [FONDI] Unit tests for funds screener

### WEEK 2 (5 issues)
6. [FONDI] Implement /api/funds/screen and /api/funds/results endpoints
7. [FONDI] Add PRO tier (AZIONI + FONDI) to pricing
8. [FONDI] Add fondi screening to scheduler (daily at 08:05)
9. [FONDI] Implement caching & data quality checks
10. [FONDI] Integration tests - full flow

### WEEK 3 (5 issues)
11. [FONDI] Deploy funds module to production
12. [ETF] Setup ETF module structure & database schema
13. [ETF] Implement Yahoo Finance data fetcher for ETFs
14. [ETF] Implement ETF screening filters
15. [ETF] Email notifier integration for ETF results

### WEEK 4 (6 issues)
16. [ETF] Unit tests for ETF screener
17. [ETF] Implement /api/etfs/screen and /api/etfs/results endpoints
18. [ETF] Add ENTERPRISE tier (AZIONI + FONDI + ETF) to pricing
19. [ETF] Add ETF screening to scheduler + combined email
20. [ALL] Deploy AZIONI + FONDI + ETF to production
21. [MAGGIO] Development complete - review + planning

---

## 🎊 QUANDO HAI CREATO IL PROJECT BOARD:

1. Dai link a GitHub:
   ```
   https://github.com/newcapitalfuerte-ally/robot-trader/projects/1
   ```

2. Inizia a muovere issues da Backlog → In Progress

3. Ogni mattina:
   - Check issues status
   - Update progress
   - Move closed issues to Done

---

## 📊 BOARD VIEW EXAMPLE

```
BACKLOG (21)          IN PROGRESS (0)    IN REVIEW (0)      DONE (0)
├─ #1                 (quando inizi)     (quando finisci)   (quando closes)
├─ #2
├─ #3
└─ ... 18 more
```

---

## 🚀 ADESSO:

Scegli:

A) **Creo il board manualmente** (20 minuti, semplice)
   └─ Tu apri GitHub, crei project, crei 21 issues

B) **Usi lo script Python** (5 minuti, automatico)
   └─ Ti do lo script, tu inserisci GitHub PAT, esegui

---

**QUALE SCEGLI?** 🎯
