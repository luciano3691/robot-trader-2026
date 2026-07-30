# ROBOT TRADER - MAGGIO 2026 DEVELOPMENT
## GitHub Project Board + Issues Breakdown

---

## 📊 PROJECT BOARD SETUP

**Repository:** https://github.com/newcapitalfuerte-ally/robot-trader
**Project Name:** ROBOT TRADER - Maggio 2026 Development
**Visibility:** Public
**Board Type:** Table View (Kanban)

### COLONNE:
1. **Backlog** - Task non iniziati
2. **In Progress** - Task in corso (max 3)
3. **In Review** - Code review/testing
4. **Done** - Completati

---

## 🎯 SPRINT 1: MAGGIO 1-7 (SETUP + FONDI WEEK 1)

### MILESTONE: May 7, 2026
### ASSIGNEE: Luciano Manicardi
### PRIORITY: P0 (Critical)

---

## 📋 ISSUE TRACKER - FONDI MODULE

### WEEK 1 (May 1-7) - SETUP & FOUNDATION

#### ISSUE #1: Setup Fondi Module Structure
```
Title: [FONDI] Setup module structure & database schema
Type: Task
Priority: P0 (Critical)
Week: Week 1 (May 1-7)
Assignee: Luciano
Estimated: 8h

Description:
- Create backend/modules/funds/ directory structure
  ├─ __init__.py
  ├─ models.py (Fund model with TER, Alpha, Sharpe, etc.)
  ├─ screener.py (FundsScreener class)
  ├─ data_fetcher.py (Yahoo Finance integration)
  └─ tests/
      └─ test_funds_screener.py

- Database schema for funds:
  ├─ Fund ID
  ├─ Name / ISIN / Ticker
  ├─ TER (%)
  ├─ Alpha (%)
  ├─ Sharpe Ratio
  ├─ Performance YTD (%)
  ├─ Volatility (Std Dev %)
  ├─ Max Drawdown (%)
  ├─ Last updated
  └─ Source (Yahoo Finance)

- Update FastAPI:
  ├─ Add /api/funds/screen endpoint (placeholder)
  ├─ Add /api/funds/results endpoint (placeholder)
  └─ Add fund tier to /api/pricing

Dependencies: None
Related: #2, #3
```

#### ISSUE #2: Yahoo Finance - Funds Data Fetcher
```
Title: [FONDI] Implement Yahoo Finance data fetcher for funds
Type: Task
Priority: P0 (Critical)
Week: Week 1 (May 1-7)
Assignee: Luciano
Estimated: 6h

Description:
- Extend yfinance to fetch fund data:
  ├─ Fund ticker search (yfinance.Ticker)
  ├─ Extract: TER, Alpha, Sharpe, Performance YTD, Volatility
  ├─ Historical data for Sharpe calculation
  ├─ Error handling (missing fields, timeouts)
  └─ Caching (Redis/file-based)

- Test on 50 European funds:
  ├─ Vanguard FTSE Developed Europe
  ├─ iShares MSCI Europe
  ├─ SPDR S&P 500 Dividend Aristocrats
  ├─ Amundi Euro STOXX 50
  └─ 46 more funds

- Log results:
  ├─ Success rate %
  ├─ Missing fields %
  ├─ Avg response time
  └─ Save to test_funds_data.json

Dependencies: #1
Related: #3
```

#### ISSUE #3: Funds Screening Logic - Parameters Implementation
```
Title: [FONDI] Implement funds screening filters
Type: Task
Priority: P0 (Critical)
Week: Week 1 (May 1-7)
Assignee: Luciano
Estimated: 8h

Description:
- Implement FundsScreener class with filters:
  ├─ TER <= 0.75% (max expense ratio)
  ├─ Alpha >= 2.0% per anno (minimum outperformance)
  ├─ Sharpe Ratio >= 0.80 (risk-adjusted return)
  ├─ Performance YTD >= 5% (minimum return)
  ├─ Volatility (Std Dev) <= 15% (max volatility)
  └─ Max Drawdown >= -20% (minimum max loss)

- Selection logic:
  ├─ Apply filters in order (efficiency)
  ├─ Log discarded funds + reason
  ├─ Calculate selection rate %
  └─ Output top 10 selected funds

- Test data:
  ├─ 200 European funds
  ├─ Expected selection rate: 5-10%
  └─ Save results to funds_screening_test.xlsx

- Code quality:
  ├─ Unit tests (pytest)
  ├─ Error handling
  └─ Logging (INFO level)

Dependencies: #1, #2
Related: #4
```

#### ISSUE #4: Funds Email Notifier - Integration
```
Title: [FONDI] Email notifier integration for funds results
Type: Task
Priority: P0 (Critical)
Week: Week 1 (May 1-7)
Assignee: Luciano
Estimated: 4h

Description:
- Extend email_notifier.py for funds:
  ├─ New email template for funds (HTML)
  ├─ Include: Fund name, TER, Alpha, Sharpe, Performance
  ├─ Top 10 funds in email body
  ├─ Excel attachment with full details
  └─ Send to: luciano@, newfrontiers65@, laura.manicardi65@

- Test:
  ├─ Send test email with 10 sample funds
  ├─ Verify attachment opens in Outlook/Gmail
  ├─ Test on mobile email client
  └─ Log: success/failure

Dependencies: #3
Related: #5
```

#### ISSUE #5: Unit Tests - Fondi Module
```
Title: [FONDI] Unit tests for funds screener
Type: Task
Priority: P1 (High)
Week: Week 1 (May 1-7)
Assignee: Luciano
Estimated: 6h

Description:
- Test file: backend/modules/funds/tests/test_funds_screener.py

Tests to implement:
├─ test_fund_model_creation() - Fund object creation
├─ test_yahoo_finance_fetch() - Data fetching
├─ test_ter_filter() - TER filter logic
├─ test_alpha_filter() - Alpha filter logic
├─ test_sharpe_filter() - Sharpe filter logic
├─ test_performance_filter() - YTD performance filter
├─ test_volatility_filter() - Volatility filter
├─ test_drawdown_filter() - Drawdown filter
├─ test_selection_rate() - Overall selection calculation
├─ test_empty_results() - Handle zero matches
└─ test_error_handling() - Invalid tickers, timeouts

- Coverage target: >= 85%
- Pytest + coverage.py

Dependencies: #1, #2, #3
Related: None
```

---

## 🎯 SPRINT 2: MAGGIO 8-14 (FONDI WEEK 2)

### MILESTONE: May 14, 2026
### PRIORITY: P0 (Critical)

#### ISSUE #6: Fondi API Endpoints
```
Title: [FONDI] Implement /api/funds/screen and /api/funds/results endpoints
Type: Task
Priority: P0 (Critical)
Week: Week 2 (May 8-14)
Assignee: Luciano
Estimated: 6h

Description:
- Extend main.py with funds endpoints:

GET /api/funds/screen
├─ Trigger funds screening
├─ Input params: (none - use defaults)
├─ Output: {status: "running", job_id: "xyz"}
└─ Queue in background (Celery/APScheduler)

GET /api/funds/results
├─ Get screening results
├─ Output: {
    "funds_analyzed": 200,
    "funds_selected": 15,
    "selection_rate": "7.5%",
    "top_funds": [
      {
        "name": "Fund X",
        "ter": 0.45,
        "alpha": 2.5,
        "sharpe": 0.95,
        "performance_ytd": 8.2,
        "volatility": 12.1,
        "max_drawdown": -18.5
      }
    ],
    "last_run": "2026-05-14 08:05:00"
  }

- Testing:
  ├─ API response time < 2 sec
  ├─ Error handling (invalid params)
  └─ Logging (all requests)

Dependencies: #1, #2, #3, #4
Related: #7
```

#### ISSUE #7: Fondi Tier Pricing - PRO Bundle
```
Title: [FONDI] Add PRO tier (AZIONI + FONDI) to pricing
Type: Task
Priority: P1 (High)
Week: Week 2 (May 8-14)
Assignee: Luciano
Estimated: 4h

Description:
- Update /api/pricing endpoint:
  ├─ BASIC (€49/mese) - AZIONI only
  ├─ PRO (€99/mese) - AZIONI + FONDI [NEW]
  └─ ENTERPRISE (€149/mese) - AZIONI + FONDI + ETF (future)

- Update Stripe webhook:
  ├─ Detect PRO tier subscription
  ├─ Enable /api/funds/screen endpoint
  ├─ Log upsell from BASIC→PRO
  └─ Email customer: "Fondi now available!"

- Update database:
  ├─ Add tier column to subscriptions
  ├─ Track feature access per tier
  └─ Log access attempts (audit trail)

Dependencies: #1
Related: #8, #20
```

#### ISSUE #8: Fondi Scheduler Integration
```
Title: [FONDI] Add fondi screening to scheduler (daily at 08:05)
Type: Task
Priority: P0 (Critical)
Week: Week 2 (May 8-14)
Assignee: Luciano
Estimated: 4h

Description:
- Update scheduler_daemon.py:
  ├─ Run value_screener.py (AZIONI) at 08:05
  ├─ Run funds_screener.py (FONDI) at 08:10 (+5 min)
  ├─ Run etf_screener.py (ETF) at 08:15 (+10 min) [future]
  └─ Send combined email with all results

- Email consolidation:
  ├─ If PRO/ENTERPRISE: include FONDI
  ├─ If ENTERPRISE: include ETF
  ├─ Single email with multiple tabs in Excel
  └─ Maintain BASIC/PRO/ENTERPRISE separation

- Logging:
  ├─ Log each screener execution
  ├─ Track email send success/failure
  └─ Monitor execution time per screener

Dependencies: #1, #2, #3, #4, #6
Related: #9, #21
```

#### ISSUE #9: Fondi Data Quality & Caching
```
Title: [FONDI] Implement caching & data quality checks
Type: Task
Priority: P1 (High)
Week: Week 2 (May 8-14)
Assignee: Luciano
Estimated: 6h

Description:
- Caching strategy:
  ├─ Cache fund data for 24h (Redis/file)
  ├─ Reduce Yahoo Finance API calls
  ├─ Faster screening results
  └─ Handle cache invalidation

- Data quality checks:
  ├─ Validate TER (0% - 3%)
  ├─ Validate Alpha (-10% to +20%)
  ├─ Validate Sharpe (-2 to +5)
  ├─ Validate Volatility (0% - 50%)
  ├─ Validate Drawdown (-100% to 0%)
  └─ Log quality issues + source

- Fallback logic:
  ├─ If field missing: use cache (if available)
  ├─ If all missing: exclude fund from screening
  └─ Log excluded funds

Dependencies: #2
Related: #10
```

#### ISSUE #10: Fondi Integration Testing
```
Title: [FONDI] Integration tests - full flow
Type: Task
Priority: P1 (High)
Week: Week 2 (May 8-14)
Assignee: Luciano
Estimated: 8h

Description:
- Full flow testing:
  ├─ Fetch 200 European funds
  ├─ Run screening filters
  ├─ Generate Excel report
  ├─ Send test email (3 recipients)
  ├─ Verify attachments open correctly
  └─ Measure total execution time

- Test scenarios:
  ├─ Happy path: 15-20 funds selected
  ├─ Edge case: 0 funds selected (send empty email?)
  ├─ Error case: Yahoo Finance timeout
  ├─ Error case: Invalid fund ticker
  └─ Performance: complete in < 5 minutes

- Output:
  ├─ Integration test report (markdown)
  ├─ funds_integration_test_results.xlsx
  ├─ Screenshots of emails
  └─ Performance metrics (timing)

Dependencies: #1-#9 (all WEEK 1-2 tasks)
Related: None
```

---

## 🎯 SPRINT 3: MAGGIO 15-21 (FONDI WEEK 3 + ETF WEEK 1)

### MILESTONE: May 21, 2026
### PRIORITY: P0 (Critical)

#### ISSUE #11: Fondi Production Deployment
```
Title: [FONDI] Deploy funds module to production
Type: Task
Priority: P0 (Critical)
Week: Week 3 (May 15-21)
Assignee: Luciano
Estimated: 6h

Description:
- Production deployment:
  ├─ Merge feature/fondi branch to master
  ├─ Run full test suite (pytest)
  ├─ Deploy Docker container
  ├─ Update production database
  ├─ Enable /api/funds/screen endpoint (PRO+)
  └─ Monitor logs for 24h

- Monitoring:
  ├─ Check API response times
  ├─ Monitor error rates
  ├─ Verify email delivery
  ├─ Track user adoption
  └─ Alert on issues

- Documentation:
  ├─ Update README.md (funds features)
  ├─ Update API docs
  ├─ Add funds parameters to user guide
  └─ Publish to docs website

Dependencies: #1-#10 (all WEEK 1-2 tasks)
Related: #12, #13
```

#### ISSUE #12: ETF Module Structure Setup
```
Title: [ETF] Setup ETF module structure & database schema
Type: Task
Priority: P0 (Critical)
Week: Week 3 (May 15-21)
Assignee: Luciano
Estimated: 8h

Description:
- Create backend/modules/etfs/ directory structure
  ├─ __init__.py
  ├─ models.py (ETF model with TER, Tracking Error, AUM, etc.)
  ├─ screener.py (ETFsScreener class)
  ├─ data_fetcher.py (Yahoo Finance integration)
  └─ tests/
      └─ test_etfs_screener.py

- Database schema for ETFs:
  ├─ ETF ID
  ├─ Name / ISIN / Ticker
  ├─ TER (%)
  ├─ Tracking Error (%)
  ├─ AUM (€ millions)
  ├─ Bid-Ask Spread (%)
  ├─ Replica Type (Physical/Synthetic)
  ├─ Fund Age (years)
  ├─ Last updated
  └─ Source (Yahoo Finance)

- Update FastAPI:
  ├─ Add /api/etfs/screen endpoint (placeholder)
  ├─ Add /api/etfs/results endpoint (placeholder)
  └─ Add ETF tier to /api/pricing

- Coverage target: >= 85%

Dependencies: None (parallel with #11)
Related: #13, #14
```

#### ISSUE #13: Yahoo Finance - ETF Data Fetcher
```
Title: [ETF] Implement Yahoo Finance data fetcher for ETFs
Type: Task
Priority: P0 (Critical)
Week: Week 3 (May 15-21)
Assignee: Luciano
Estimated: 6h

Description:
- Extend yfinance to fetch ETF data:
  ├─ ETF ticker search
  ├─ Extract: TER, AUM, Bid-Ask Spread, Tracking Error
  ├─ Determine: Replica type (physical vs synthetic)
  ├─ Estimate: Fund age from inception date
  ├─ Error handling
  └─ Caching (Redis/file-based)

- Test on 100 European ETFs:
  ├─ iShares (Core MSCI World, Developed Europe, etc.)
  ├─ Vanguard (FTSE Developed Europe, etc.)
  ├─ SPDR (S&P 500, etc.)
  ├─ Amundi (MSCI World, etc.)
  └─ 96 more ETFs

- Log results:
  ├─ Success rate %
  ├─ Missing fields %
  ├─ Avg response time
  └─ Save to test_etfs_data.json

Dependencies: #12
Related: #14
```

#### ISSUE #14: ETF Screening Logic - Parameters Implementation
```
Title: [ETF] Implement ETF screening filters
Type: Task
Priority: P0 (Critical)
Week: Week 3 (May 15-21)
Assignee: Luciano
Estimated: 8h

Description:
- Implement ETFsScreener class with filters:
  ├─ TER <= 0.15% (max expense ratio)
  ├─ Tracking Error <= 0.10% (max deviation from benchmark)
  ├─ AUM >= €50M (minimum assets under management)
  ├─ Bid-Ask Spread <= 0.05% (maximum spread)
  ├─ Replica Type = PHYSICAL (preference)
  └─ Fund Age >= 2 anni (minimum track record)

- Selection logic:
  ├─ Apply filters in order (efficiency)
  ├─ Log discarded ETFs + reason
  ├─ Calculate selection rate %
  ├─ Bonus points for Physical replicas
  └─ Output top 15 selected ETFs

- Test data:
  ├─ 300 European ETFs
  ├─ Expected selection rate: 8-12%
  └─ Save results to etfs_screening_test.xlsx

- Code quality:
  ├─ Unit tests (pytest)
  ├─ Error handling
  └─ Logging (INFO level)

Dependencies: #12, #13
Related: #15
```

#### ISSUE #15: ETF Email Notifier - Integration
```
Title: [ETF] Email notifier integration for ETF results
Type: Task
Priority: P0 (Critical)
Week: Week 3 (May 15-21)
Assignee: Luciano
Estimated: 4h

Description:
- Extend email_notifier.py for ETFs:
  ├─ New email template for ETFs (HTML)
  ├─ Include: ETF name, TER, AUM, Tracking Error, Spread
  ├─ Top 15 ETFs in email body
  ├─ Excel attachment with full details
  └─ Send to: luciano@, newfrontiers65@, laura.manicardi65@

- Test:
  ├─ Send test email with 15 sample ETFs
  ├─ Verify attachment opens in Outlook/Gmail
  ├─ Test on mobile email client
  └─ Log: success/failure

Dependencies: #14
Related: #16
```

---

## 🎯 SPRINT 4: MAGGIO 22-28 (ETF WEEK 2-3)

### MILESTONE: May 28, 2026
### PRIORITY: P0 (Critical)

#### ISSUE #16: Unit Tests - ETF Module
```
Title: [ETF] Unit tests for ETF screener
Type: Task
Priority: P1 (High)
Week: Week 4 (May 22-28)
Assignee: Luciano
Estimated: 8h

Description:
- Test file: backend/modules/etfs/tests/test_etfs_screener.py

Tests to implement:
├─ test_etf_model_creation()
├─ test_yahoo_finance_fetch()
├─ test_ter_filter()
├─ test_tracking_error_filter()
├─ test_aum_filter()
├─ test_spread_filter()
├─ test_replica_type_preference()
├─ test_fund_age_filter()
├─ test_selection_rate()
├─ test_empty_results()
└─ test_error_handling()

- Coverage target: >= 85%

Dependencies: #12, #13, #14
Related: #17
```

#### ISSUE #17: ETF API Endpoints
```
Title: [ETF] Implement /api/etfs/screen and /api/etfs/results endpoints
Type: Task
Priority: P0 (Critical)
Week: Week 4 (May 22-28)
Assignee: Luciano
Estimated: 6h

Description:
- Extend main.py with ETF endpoints (similar to FONDI #6)

GET /api/etfs/screen
├─ Trigger ETF screening
├─ Output: {status: "running", job_id: "xyz"}

GET /api/etfs/results
├─ Get screening results
├─ Output: {
    "etfs_analyzed": 300,
    "etfs_selected": 35,
    "selection_rate": "11.7%",
    "top_etfs": [
      {
        "name": "ETF X",
        "ter": 0.08,
        "aum_millions": 2500,
        "tracking_error": 0.04,
        "spread": 0.02,
        "replica_type": "Physical",
        "age_years": 8
      }
    ],
    "last_run": "2026-05-28 08:15:00"
  }

Dependencies: #12, #13, #14, #15
Related: #18
```

#### ISSUE #18: ETF Tier Pricing - ENTERPRISE Bundle
```
Title: [ETF] Add ENTERPRISE tier (AZIONI + FONDI + ETF) to pricing
Type: Task
Priority: P1 (High)
Week: Week 4 (May 22-28)
Assignee: Luciano
Estimated: 4h

Description:
- Update /api/pricing endpoint:
  ├─ BASIC (€49/mese) - AZIONI only
  ├─ PRO (€99/mese) - AZIONI + FONDI
  └─ ENTERPRISE (€149/mese) - AZIONI + FONDI + ETF [NEW]

- Update Stripe webhook:
  ├─ Detect ENTERPRISE tier subscription
  ├─ Enable /api/etfs/screen endpoint
  ├─ Log upsell from PRO→ENTERPRISE
  └─ Email customer: "ETF screening now available!"

- Update database:
  ├─ Track feature access per tier
  └─ Log access attempts (audit trail)

Dependencies: #7 (from FONDI)
Related: #19, #20
```

#### ISSUE #19: ETF Scheduler Integration & Combined Email
```
Title: [ETF] Add ETF screening to scheduler + combined email
Type: Task
Priority: P0 (Critical)
Week: Week 4 (May 22-28)
Assignee: Luciano
Estimated: 6h

Description:
- Update scheduler_daemon.py:
  ├─ Run value_screener.py (AZIONI) at 08:05
  ├─ Run funds_screener.py (FONDI) at 08:10
  ├─ Run etf_screener.py (ETF) at 08:15
  └─ Send SINGLE consolidated email

- Email consolidation (example for ENTERPRISE):
  ├─ Subject: "Daily Markets: Stocks | Funds | ETFs"
  ├─ Body: HTML with 3 tabs
  │   ├─ Tab 1: Top 7 Azioni (stocks)
  │   ├─ Tab 2: Top 10 Fondi (funds)
  │   └─ Tab 3: Top 15 ETF
  ├─ Attachment: robot_trader_YYYYMMDD.xlsx (4 sheets)
  │   ├─ Sheet 1: AZIONI (7 stocks)
  │   ├─ Sheet 2: FONDI (10 funds)
  │   ├─ Sheet 3: ETF (15 ETFs)
  │   └─ Sheet 4: Portfolio Summary
  └─ Send to 3 recipients

- Tier-specific emails:
  ├─ BASIC: Only AZIONI tab + sheet
  ├─ PRO: AZIONI + FONDI tabs + sheets
  └─ ENTERPRISE: AZIONI + FONDI + ETF tabs + sheets

- Logging & monitoring:
  ├─ Log each screener execution
  ├─ Track email send success/failure
  ├─ Monitor total execution time
  └─ Alert on failures

Dependencies: #1-#18 (all modules)
Related: #20, #21
```

#### ISSUE #20: Production Deployment - All Modules
```
Title: [ALL] Deploy AZIONI + FONDI + ETF to production
Type: Task
Priority: P0 (Critical)
Week: Week 4 (May 22-28)
Assignee: Luciano
Estimated: 8h

Description:
- Production deployment:
  ├─ Merge feature/fondi + feature/etf branches to master
  ├─ Run full test suite (pytest - all modules)
  ├─ Deploy Docker container
  ├─ Update production database
  ├─ Update Stripe webhook (new tiers)
  ├─ Enable all endpoints (/api/azioni/*, /api/fondi/*, /api/etf/*)
  ├─ Deploy scheduler with combined email
  └─ Monitor logs for 48h

- Pre-deployment checklist:
  ├─ [ ] All tests passing (>85% coverage)
  ├─ [ ] No console errors/warnings
  ├─ [ ] Database migrations successful
  ├─ [ ] Stripe webhooks functional
  ├─ [ ] Email delivery verified
  ├─ [ ] Performance tests OK (<3 sec per endpoint)
  └─ [ ] Documentation updated

- Post-deployment monitoring:
  ├─ API uptime monitoring
  ├─ Error rate tracking
  ├─ Email delivery rate
  ├─ User adoption per tier
  ├─ Performance metrics (latency, throughput)
  └─ Alert thresholds configured

- Rollback plan (if needed):
  ├─ Immediate: Revert to previous Docker image
  ├─ DNS failover ready
  ├─ Database backup taken
  └─ Runbook documented

Dependencies: #1-#19 (all tasks)
Related: #21
```

#### ISSUE #21: Maggio Development Complete - Post-Mortem & Planning
```
Title: [MAGGIO] Development complete - review + planning
Type: Task
Priority: P1 (High)
Week: Week 4 (May 22-28)
Assignee: Luciano
Estimated: 6h

Description:
- Maggio retrospective:
  ├─ What went well?
  ├─ What could be better?
  ├─ Blockers faced + solutions
  ├─ Performance metrics (lines of code, test coverage, etc.)
  └─ Time spent vs estimated

- Metrics:
  ├─ Total hours spent vs 160h planned
  ├─ Test coverage: FONDI % + ETF %
  ├─ Bug discovery rate
  ├─ Code quality score
  └─ Team velocity

- GIUGNO planning:
  ├─ Launch FONDI publicly (July 1 → upsell BASIC→PRO!)
  ├─ User feedback loop
  ├─ Performance optimization
  ├─ Advanced features roadmap
  └─ Marketing materials

- Documentation:
  ├─ Write maggio development summary (markdown)
  ├─ Update README.md with new features
  ├─ Update API documentation
  ├─ Create user guide for FONDI + ETF
  └─ Create troubleshooting guide

Dependencies: #1-#20 (all tasks)
Related: None
```

---

## 📊 TIMELINE SUMMARY

```
MAGGIO 2026:
├─ Week 1 (May 1-7):
│  └─ FONDI Module foundation (5 issues: #1-#5)
│     Setup, data fetcher, screening, email, tests
│     Status: Backlog → In Progress
│
├─ Week 2 (May 8-14):
│  └─ FONDI Module completion (5 issues: #6-#10)
│     API endpoints, pricing tier, scheduler, caching, integration tests
│     Status: Backlog (waiting Week 1 completion)
│
├─ Week 3 (May 15-21):
│  ├─ FONDI Production deployment (#11)
│  └─ ETF Module foundation (4 issues: #12-#15)
│     Setup, data fetcher, screening, email
│     Status: Backlog (parallel with FONDI #11)
│
└─ Week 4 (May 22-28):
   ├─ ETF Module completion (4 issues: #16-#19)
   │  Unit tests, API, pricing, scheduler + combined email
   ├─ Production deployment (#20)
   └─ Retrospective + GIUGNO planning (#21)
      Status: Backlog

TOTALE ISSUES: 21 + 1 retrospective = 22
TOTALE ESTIMATED HOURS: ~160h (32h/week)
ESTIMATED COMPLETION: May 28, 2026
```

---

## 🎯 DEPENDENCIES MAP

```
#1 FONDI Setup
├─ #2 Yahoo Finance FONDI
├─ #3 Screening Logic FONDI
│  ├─ #4 Email Notifier FONDI
│  └─ #5 Unit Tests FONDI
├─ #6 API Endpoints FONDI
├─ #7 PRO Tier Pricing
├─ #8 Scheduler Integration FONDI
├─ #9 Caching & Data Quality
├─ #10 Integration Tests FONDI
└─ #11 Production Deployment FONDI
   ├─ #12 ETF Setup (parallel)
   ├─ #13 Yahoo Finance ETF
   ├─ #14 Screening Logic ETF
   ├─ #15 Email Notifier ETF
   ├─ #16 Unit Tests ETF
   ├─ #17 API Endpoints ETF
   ├─ #18 ENTERPRISE Tier Pricing
   ├─ #19 Scheduler Integration ETF + Combined Email
   └─ #20 Production Deployment ALL
      └─ #21 Retrospective & GIUGNO Planning
```

---

## 🚀 PRIORITY MATRIX

| Priority | Issues | Blockers |
|----------|--------|----------|
| P0 (Critical) | #1,#2,#3,#4,#6,#8,#11,#12,#13,#14,#15,#17,#19,#20 | FONDI Week1→Week2→Week3 |
| P1 (High) | #5,#7,#9,#10,#16,#18,#21 | ETF Week3→Week4 |
| P2 (Medium) | None | - |

---

## ✅ ACCEPTANCE CRITERIA - MAGGIO COMPLETE

- [ ] All 21 issues closed
- [ ] FONDI module live in production (PRO tier)
- [ ] ETF module live in production (ENTERPRISE tier)
- [ ] Combined email working (08:05, 08:10, 08:15)
- [ ] Test coverage >= 85% (all modules)
- [ ] Zero critical bugs in prod
- [ ] Customer upsells: BASIC→PRO (target: 25%)
- [ ] Scheduler running stable (24h+ uptime)
- [ ] MRR trajectory: €4,900 (Apr) → €49,955 (Jul)

---

## 📝 NOTES

- All timestamps in UTC+2 (CEST - Canary Islands summer time)
- All times relative to 08:05 daily execution
- Feature flags: Use STRIPE_TIER to control access
- Monitoring: Datadog/New Relic for prod metrics
- Backup: Daily database snapshot (AWS S3)
- Support: Help desk for tier-specific issues
