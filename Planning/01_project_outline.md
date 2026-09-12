# Money Tracking App — Full Project Outline
**Step 1 of 6 — Project Outline**
**Status:** Draft v3 — Steps 1 & 2 complete (scope + architecture decisions locked). Moving into Step 3 (agent structure).

---

## 1. Vision Statement

A personal finance app (mobile + web) that lets users log income and expenses, organize them into custom categories, see monthly trends, and receive an automatically-generated budget based on their own history — with a manual fallback for new users who have no history yet.

The core differentiator vs. a plain spreadsheet: **zero-setup budgeting intelligence**. The app watches the user's real behavior for 3 months and then tells them what their budget *should* be, instead of asking them to guess.

---

## 2. Goals & Success Criteria

| Goal | How we'll know it worked |
|---|---|
| Fast, frictionless transaction entry | Adding a transaction takes < 10 seconds, < 4 taps |
| Meaningful categorization | User can see spend-by-category per month without manual math |
| Automatic budgeting | After 3 months of data, app proposes a budget with no user input required |
| Cold-start usability | A user with zero history can still get value on day 1 (manual budget input) |
| Cross-platform parity | Core features work identically on mobile app and web app |
| Trustworthy with money data | No data loss, accurate math, secure auth, encrypted sensitive data |

---

## 3. Target Users / Personas — **DECIDED**

- **Primary:** Individual users tracking personal finances. **Single-user only for v1** — no shared/family accounts.
- Comfortable with mobile apps, wants something faster than a spreadsheet but simpler than a full accounting tool (not competing with YNAB/Mint feature-for-feature at launch).

---

## 4. Core Features (MVP scope)

### 4.1 Transactions (Income & Expenses)
- Add a transaction: amount, type (income/expense), category, date, optional note.
- Edit / delete transactions.
- List/history view, filterable by month, category, type.

### 4.2 Categories
- Predefined starter categories (e.g., Food, Transport, Housing, Salary, etc.) so the app is usable immediately.
- User can create, rename, delete (or archive) custom categories.
- Each category tagged as Income or Expense (a category shouldn't mix both).
- **DECIDED:** each Expense category can be manually tagged by the user as "essential" or "discretionary." This tag feeds directly into the budgeting engine (see 4.4). Default suggestion at category creation (e.g. Housing/Utilities pre-checked as essential) is a nice-to-have UX detail, not a blocker — user always has final say.

### 4.3 Monthly Tracking
- All money movements are grouped and summarized by calendar month.
- Monthly dashboard: total income, total expenses, net (saved/overspent), breakdown by category (chart).
- Month-over-month comparison (this month vs last month, vs 3-month average).

### 4.4 Automatic Budget Engine
- **With ≥3 months of history:** compute a suggested budget per category based on historical averages. Essential-tagged categories (per user's manual tagging, Section 4.2) are budgeted with less slack/more priority than discretionary ones. **The budget is presented as two separate totals — an Essentials budget and a Discretionary/Non-essentials budget — each computed from its own 3-month weighted average with outlier trimming, rather than one blended number.** This lets the user see at a glance how much of their income is locked into needs vs. how much is flexible spending money.
- **With <3 months of history (cold start):** user manually inputs expected income and, optionally, expected expenses per category at onboarding; app tracks against this until real history accumulates.
- Budget should update/re-suggest as new months of data come in (rolling 3-month window).
- User can accept, edit, or override the suggested budget per category.

### 4.5 Accounts / Auth
- User registration/login (Step 2 will decide the auth provider/infrastructure).
- Basic profile: currency preference, month cycle.
- **DECIDED:** MVP uses strict calendar months (1st–end of month). Custom/pay-day-aligned cycles are backlog (Section 5).

---

## 5. Non-Core / Backlog Features (explicitly OUT of MVP unless you want to pull them in)

### 5.1 Priority fast-follow (post-MVP, first in line right after launch)
- Custom/pay-day-aligned month cycles *(MVP uses calendar month — see Section 4.5)*
- Budget alerts/notifications (e.g., "You've spent 90% of your Food budget")
- Data export **and import** (CSV/PDF reports out; CSV/spreadsheet import in — useful for users migrating from a spreadsheet or another app)
- Multi-device real-time sync (vs. just cloud-backed sync on app open)

### 5.2 Later backlog (no committed timing yet)
- Multi-currency support / conversion
- Shared/family accounts, multi-user budgets *(confirmed out of scope for v1 — see Section 3)*
- Bank account sync / auto-import transactions (Plaid-style)
- Recurring transaction automation (e.g., auto-log rent every 1st)
- Savings goals / debt payoff tracking
- Receipt photo attachment / OCR

---

## 6. Platforms

- **Mobile app** (iOS/Android — need to decide native vs. cross-platform in Step 2)
- **Web app** (responsive, same core functionality)
- Shared backend/API serving both — single source of truth for data.

---

## 7. Non-Functional Requirements

- **Security & privacy:** this is financial data — needs encryption at rest and in transit, secure auth (no plaintext passwords), sensible session handling. Even if we don't do bank-sync in v1, users will treat this as sensitive.
- **Data integrity:** transaction math must be exact (careful with floating point — use fixed-point/decimal handling, not raw floats).
- **Offline tolerance:** should the mobile app allow adding transactions offline and sync later? (open question for Step 2 — affects architecture a lot.)
- **Performance:** monthly dashboards should load fast even after years of data (pagination/aggregation strategy needed).
- **Scalability:** doesn't need to be enterprise-scale on day 1, but shouldn't paint us into a corner (Step 2).
- **Maintainability:** since this is Python-first, favor clear modular architecture so specialized agents (Step 3) can own separate components without stepping on each other.

---

## 8. High-Level User Flows (to detail further later)

1. **Onboarding (no history):** Sign up → set currency/month cycle → input expected income → optionally set up categories & rough budget → land on empty dashboard.
2. **Daily use:** Open app → quick-add transaction → pick category → done.
3. **Monthly review:** Open dashboard → see income/expense/net for the month → drill into a category → compare to budget.
4. **Budget generation (3+ months in):** App auto-computes and presents a suggested budget → user reviews/edits → accepts.
5. **Category management:** Create/edit/archive categories at any time without breaking historical data integrity.

---

## 9. Step 2 — Key Project Decisions

| # | Decision | Choice | Notes |
|---|---|---|---|
| 1 | Platform strategy | **Flutter** (mobile + web, single codebase) | Backend stays Python — Flutter is the client layer only |
| 2 | Auth | **Supabase Auth** | Chosen partly because it pairs with the DB decision below |
| 3 | Database | **PostgreSQL, via Supabase** | Supabase's managed Postgres *is* our DB — one vendor for DB + Auth, one less service to run |
| 4 | Backend framework | **FastAPI (Python)** | API-first, async, Pydantic validation (enforce `Decimal` for all money fields, never `float`) |
| 5 | Hosting | **Render** (FastAPI backend) | Supabase hosts DB + Auth; Render hosts the API. Clean migration path to AWS/GCP later if scale demands it |
| 6 | Offline support | **Online-only for MVP**, offline sync is a fast-follow | Simplifies MVP architecture significantly |
| 7 | Budgeting algorithm | **Weighted rolling 3-month average with outlier trimming, computed separately for essential vs. discretionary categories** | Recent month weighted slightly higher; one-off large expenses excluded so they don't skew a category's budget. Essentials and discretionary get their own budget totals/lines (not blended into one number) — see 4.4 |

---

## 10. Phased Roadmap (mirrors your 6-step process)

1. ✅ Full project outline
2. ✅ Key project decisions (tech stack, infra, architecture)
3. ✅ Specialized agent definitions + task division + PM-agent oversight model *(see `02_agent_structure.md`)*
4. ✅ Testing strategy & iterative QA cycle *(see `03_testing_strategy.md`)*
5. ✅ Production infrastructure setup *(see `04_production_infrastructure.md`)*
6. ⬜ Launch

---

## 11. Initial Risk Watch-list

- **Floating point/currency math errors** — mitigate with `Decimal` type from day one, not floats.
- **Budget engine giving bad suggestions with sparse/noisy data** — needs a defined algorithm and edge-case handling (e.g., a single huge one-time expense skewing the average).
- **Scope creep** — the backlog in Section 5 is attractive; recommend we lock MVP scope before Step 3 (agent division) so agents aren't building a moving target.
- **Cross-platform parity drift** — mobile and web diverging in behavior if they don't share a backend/API cleanly.

---

*Next step: Step 3 — Specialized agent definitions, task division, and the PM-agent oversight model.*
