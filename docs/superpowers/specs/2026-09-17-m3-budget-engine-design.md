# M3 — Budget Engine — Design

**Builds on:** M1 (auth + transaction CRUD) and M2 (per-user categories,
monthly summary, dashboard, navigation shell) — both merged to `main`, live
on Render + Supabase. `Planning/02_agent_structure.md`'s milestone table
scopes M3 as "Budget suggestion endpoint (cold-start + 3-month engine,
essentials/discretionary split)" (backend) / "Budget input (cold-start),
budget display/edit UI" (frontend). Algorithm decided in
`Planning/01_project_outline.md` §4.4/§9-row-7: weighted rolling 3-month
average with outlier trimming, computed separately for Essentials vs.
Discretionary.

**Status:** Approved design, ready for implementation planning.

---

## Problem

M1/M2 tagged "essential vs. discretionary" on the **category**
(`categories.is_essential`). Brainstorming for M3 surfaced that this is the
wrong axis: real spending within a single category mixes both — groceries
(essential) and dining out (discretionary) are both "Food." Before building
a budget engine on top of a category-level tag, the tag itself needs to move
to the **transaction**, where it actually varies.

M3 therefore does two things: (1) moves the essential/discretionary tag from
category to transaction, and (2) builds the budget suggestion engine and its
UI on top of that corrected model.

## Scope decisions (confirmed during brainstorming)

1. **`is_essential` moves from `categories` to `transactions`.** Nullable —
   only meaningful for expense transactions; income transactions never carry
   it. Required (service-layer validation, not a DB constraint — same
   pattern as the existing type/category coherence check) for every new
   expense transaction. Existing transactions are backfilled to `NULL`
   ("unclassified") rather than a guessed default; the budget engine simply
   skips `NULL` rows.
2. **No category-level default.** The category form loses its essential
   toggle entirely. Every expense transaction requires an explicit
   essential/discretionary choice at entry — accepted trade-off against the
   outline's <10s/≤4-tap goal, per explicit user decision.
3. **Per-category budgets, split by tag.** Each category can produce up to
   two independent budget lines — e.g. "Food (essential)" and "Food
   (discretionary)" — each computed only from transactions carrying that
   exact tag. Essentials/Discretionary grand totals are the sum of their
   respective lines.
4. **Cold-start is per-line, not per-account or per-category.** A line
   `(category_id, is_essential)` qualifies for a computed suggestion only
   once it has its own 3 months of matching transaction history. A brand-new
   category, or a category that's never had a discretionary transaction,
   stays cold-start on that specific line even if the account is older.
5. **Budgets are standing targets, not monthly resets.** Once set (cold-start
   manual entry, accepted suggestion, or a manual override), a line's amount
   persists unchanged until the user edits it or explicitly requests a fresh
   suggestion. No forced monthly re-approval.
6. **Income target is always manual, indefinitely.** `expected income` from
   the outline's cold-start flow doesn't disappear once real history exists
   — it stays a user-maintained standing value (`income_targets`), never
   computed. Actual income is separately observed from real transactions
   (same aggregation the M2 summary already does).
7. **Weighting: 3:2:1** (newest:middle:oldest month) for the 3-month
   average. Flagged for a future update: letting the user choose a broader
   financial goal (save/invest/spend) that could adjust this — out of scope
   for M3, noted as backlog.
8. **Outlier trim: median-deviation rule.** For a line's 3 monthly totals,
   if the highest is more than 2× the median of the other two, drop it and
   average the remaining 2 months weighted 2:1 (recent:older). Only ever
   trims a high outlier — a zero or low month is real data, not noise.
9. **Storage: two tables**, not one overloaded table — `income_targets`
   (one manual scalar per user) and `budgets` (category+tag spending lines),
   both fully `NOT NULL`. Cleaner than a single table with a nullable
   `category_id` standing in for "this row is actually the income target."
10. **Both a projected view and an actual-vs-budget view**, and they're
    complementary, not either/or:
    - **Projected net** = income target − (essentials budget total +
      discretionary budget total). Forward-looking: "if you stick to this
      plan, you'll save/overspend $X" — computed live, never persisted.
    - **Actual vs. budget** = this month's real transactions (from the same
      aggregation M2's summary already does) compared against each budget
      line, and rolled up into Essentials/Discretionary/overall actual
      totals and an `actual_net_so_far`.
11. **Budget UI gets its own tab.** `HomeShell`'s navigation grows from 3 to
    4 tabs: Dashboard / Add / Categories / **Budget**. Keeps "what
    happened" (Dashboard) separate from "what should I spend" (Budget), and
    leaves room to grow (e.g. the future goal-based weighting from #7).

## Data model changes

- `categories.is_essential` — **dropped**.
- `transactions.is_essential` — **added**, `BOOLEAN NULL`. Required for new
  expense transactions (service-layer 422 if missing), forbidden/ignored for
  income. Existing rows backfilled `NULL`.
- **New table `income_targets`**: `id`, `user_id UUID NOT NULL UNIQUE`,
  `amount NUMERIC NOT NULL`, `updated_at`. Upserted directly by the user.
- **New table `budgets`**: `id`, `user_id UUID NOT NULL`,
  `category_id UUID NOT NULL`, `is_essential BOOLEAN NOT NULL`,
  `amount NUMERIC NOT NULL`,
  `source TEXT NOT NULL` (`'computed' | 'manual'` — a user-typed amount is
  always `'manual'` whether it's a cold-start entry or an override of a
  computed line; there's no separate `'cold_start'` value since nothing
  ever writes one, per the `PUT /budget/lines` behavior below),
  `updated_at`. Unique on `(user_id, category_id, is_essential)`.
  `source` is provenance for display only ("you set this" vs. "computed
  from your history") — it doesn't change how the line behaves once set.

### Migration

Same pre-launch-data posture as M2's migration 0002: the live Supabase
project currently holds only smoke-test data from click-through
verification. The migration:

1. Adds `transactions.is_essential` (`BOOLEAN NULL`), backfilling existing
   rows to `NULL` — no data loss, no guessed values.
2. Drops `categories.is_essential`.
3. Creates `income_targets` and `budgets` (empty on creation — no seed
   data, matching the lazy/on-demand posture of everything else in this
   app).

Reversible downgrade: drops `income_targets`/`budgets`, drops
`transactions.is_essential`, re-adds `categories.is_essential` (as
nullable — cannot restore the original per-user values, same caveat as
migration 0002's downgrade not restoring deleted rows).

## Backend algorithm

For a line `(user_id, category_id, is_essential)`:

1. **Window:** the 3 calendar months immediately preceding the current
   (in-progress) month.
2. **Eligibility:** the line qualifies for a computed suggestion only if
   *each* of those 3 months has at least one transaction matching that
   exact `(category_id, is_essential)` pair. Otherwise: "not enough data
   yet" (cold-start).
3. **Outlier trim:** compute the median of the 3 months' totals. If the
   highest is more than 2× that median, drop it and average the remaining
   2 months weighted 2:1 (more recent : older).
4. **Weighting (no outlier):** `(3×newest + 2×middle + 1×oldest) / 6`.
5. Result is a `Decimal`, quantized to 2 places with `ROUND_HALF_UP` — the
   codebase has no prior explicit rounding convention (money fields rely on
   `Numeric(12, 2)` column precision alone), so this introduces the first
   one; `ROUND_HALF_UP` matches ordinary human expectations for a
   user-facing suggested amount. This is a **preview** — returned by `GET
   /api/v1/budget/suggestions`, only written into `budgets` (as
   `source='computed'`) via the explicit accept action.

Income target has no algorithm — always the manual value in
`income_targets`.

## Backend API

All routes under `/api/v1/budget`, auth-protected, scoped to the caller,
validated against non-archived expense categories the caller owns.

- **`GET /api/v1/budget?month=YYYY-MM`** (default current month, same
  regex/validation as the M2 summary endpoint) — full screen state in one
  call:
  - `income_target` (amount or `null` if unset), `actual_income_this_month`
    (actual income for the requested month)
  - `lines`: array of `{category_id, category_name, is_essential,
    budget_amount (nullable), source (nullable), eligible_for_suggestion,
    actual_this_month}` (`actual_this_month` is for the requested month). A
    line appears only if it has a saved budget or any transaction history
    for that exact category+tag.
  - `essentials_budget_total`, `discretionary_budget_total`
  - `essentials_actual_total`, `discretionary_actual_total` (for the
    requested month)
  - `projected_net` = `income_target − (essentials_budget_total +
    discretionary_budget_total)` — independent of the requested month,
    since budgets are standing targets, not month-specific
  - `actual_net_so_far` = `actual_income_this_month − (essentials_actual_total
    + discretionary_actual_total)` — for the requested month
  - `eligible_for_suggestion` and `source` are always based on the true
    current date, never on the requested `month` — a line's cold-start
    status doesn't change depending on which past month you're viewing
    actuals for.
- **`PUT /api/v1/budget/income-target`** — body `{amount}`. Upserts
  `income_targets`.
- **`PUT /api/v1/budget/lines`** — body `{category_id, is_essential,
  amount}`. Upserts a `budgets` row with `source='manual'`. Covers both
  cold-start entry and overriding a computed suggestion.
- **`POST /api/v1/budget/lines/accept-suggestion`** — body `{category_id,
  is_essential}`. Recomputes server-side and persists as `source='computed'`.
  422 if the line isn't currently eligible.
- **`GET /api/v1/budget/suggestions`** — array of freshly computed
  `{category_id, is_essential, suggested_amount}` for every currently
  eligible line — lets the UI show "suggested: $X" before committing.

Service layer: `app/services/budget.py` (algorithm + line/income-target CRUD
+ the aggregate `GET /budget` query), schemas in `app/schemas/budget.py`.

### Cross-cutting changes

- `app/services/transactions.py` (`create_transaction`, `update_transaction`):
  validate `is_essential` is present when `type='expense'`, rejected when
  `type='income'` — 422 on violation.
- `app/services/categories.py` / `app/schemas/category.py`: remove
  `is_essential` entirely (field, validation, default-category seed data).

## Frontend

- **Navigation:** `HomeShell`'s `NavigationBar` grows to 4 tabs:
  Dashboard / Add / Categories / **Budget**.
- **`transaction_entry_screen.dart`:** adds a required Essential/
  Discretionary segmented toggle, shown only when type is Expense — mirrors
  the existing category-picker reaction to the Income/Expense toggle.
- **`category_form_screen.dart`:** essential/discretionary toggle removed.
- **New `lib/features/budget/`:**
  - `models/budget_state.dart` — `BudgetLine {categoryId, categoryName,
    isEssential, budgetAmount, source, eligibleForSuggestion,
    actualThisMonth}` and `BudgetState {incomeTarget,
    actualIncomeThisMonth, lines, essentialsBudgetTotal,
    discretionaryBudgetTotal, essentialsActualTotal,
    discretionaryActualTotal, projectedNet, actualNetSoFar}`.
  - `providers/budget_provider.dart` — `budgetProvider` as
    `FutureProvider.autoDispose<BudgetState>` (same staleness lesson as the
    M2 dashboard bug — this screen is also torn down on tab switch), plus
    notifier methods for editing the income target, editing/accepting a
    line, invalidating the provider after a successful write.
  - `screens/budget_screen.dart` — top: income target (editable) vs. actual
    income, projected net and actual-net-so-far side by side. Below:
    Essentials and Discretionary sections, each with its budget-vs-actual
    totals, then its category lines. A line with a saved budget shows an
    actual-vs-budget progress indicator; a line with none yet shows "Get
    suggestion" (if eligible) or a manual amount input (cold-start).

## Testing

**Backend (pytest):**
- Algorithm: 3:2:1 weighting, outlier trim (outlier in newest/middle/oldest
  month, and no-outlier case), eligibility requiring all 3 months present,
  `Decimal` precision throughout.
- `income_targets`: upsert create vs. update, cross-user isolation.
- `budgets`: manual upsert (category must be expense-type, non-archived,
  owned by caller), `accept-suggestion` (persists `source='computed'`, 422
  when ineligible), cross-user isolation.
- `GET /api/v1/budget`: totals, `projected_net`, `actual_net_so_far`, and
  per-line `actual_this_month` aggregate correctly; a line only appears with
  a budget or matching transaction history.
- `GET /api/v1/budget/suggestions`: only eligible lines appear, correct
  amounts.
- Transaction create/update: `is_essential` required (422) for
  `type=expense`, rejected for `type=income`.
- Migration: `categories.is_essential` dropped; `transactions.is_essential`
  added nullable, existing rows backfilled `NULL`.

**Frontend (`flutter test`):** `BudgetScreen` renders totals/lines/
projected-net from a fake state; `TransactionEntryScreen` test updated for
the required essential toggle (expense-only); `CategoryFormScreen` test
updated to confirm the toggle is gone.

**Manual click-through** (standing rule): after each major piece lands —
the is_essential migration from category to transaction, the budget
endpoints, the Budget screen — click through it live (real login, real
backend, real Supabase) before moving to the next feature.

## Out of scope for M3

- Month-over-month / 3-month-average trend comparison on the dashboard
  (outline §4.3) — explicitly deferred to a future update.
- User-selectable financial goal (save/invest/spend) affecting the
  weighting scheme — flagged as a future update, not built now.
- Logout/sign-out flow and missing back buttons — flagged during this
  brainstorming session as needed before production, tracked for M4
  (Polish & Edge Cases), not part of M3.
- Any charting library — the Budget screen uses the same simple
  proportional-bar approach as the M2 dashboard, no new dependency.
