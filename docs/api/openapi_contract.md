# MoneyTracker API Contract

Machine-readable schema: `docs/api/openapi.json` (regenerate with
`python backend/scripts/export_openapi.py` any time endpoints change).

## Auth

Every endpoint below requires `Authorization: Bearer <supabase-jwt>`.
Missing/invalid/expired token → `401`.

*Note: The OpenAPI schema marks the `Authorization` header as optional for technical reasons (to return a cleaner 401 rather than 422 when missing), but it is enforced at runtime — Frontend must always send it.*

## `POST /api/v1/transactions`

Request body:
```json
{
  "category_id": "uuid",
  "type": "income | expense",
  "amount": "12.50",
  "occurred_on": "2026-09-01",
  "note": "optional string, max 280 chars",
  "is_essential": true
}
```
`amount` is a decimal string, positive, at most 2 decimal places.
`is_essential` tags an *expense* transaction as essential (`true`) or
discretionary (`false`) spending; it must be provided (non-null) for
expenses and must be omitted/null for income. Legacy/backfilled rows may
still have `is_essential = null` on an expense (see `GET /api/v1/budget`
below for how that's handled).
Response `201`: `TransactionRead` (adds `id`, `user_id`, `created_at`, `updated_at`).
`422` if request body is invalid/malformed (Pydantic validation error).

## `GET /api/v1/transactions`

Response `200`: array of `TransactionRead`, scoped to the caller, newest `occurred_on` first.

## `GET /api/v1/transactions/{transaction_id}`

Response `200`: `TransactionRead`. `404` if not found or not owned by caller.

## `PATCH /api/v1/transactions/{transaction_id}`

Request body: any subset of the `POST` fields. Response `200`: updated `TransactionRead`.
`422` if request body is invalid/malformed (Pydantic validation error).

## `DELETE /api/v1/transactions/{transaction_id}`

Response `204`.

## `GET /api/v1/categories`

Query param `include_archived` (bool, default `false`). Response `200`: array of
`CategoryRead` (`id`, `name`, `type`, `is_archived`), scoped to the caller. A
brand-new user's 7 starter categories are created lazily on first read.

## `POST /api/v1/categories`

Request body: `{"name": "...", "type": "income | expense"}`. Response `201`: `CategoryRead`.

## `PATCH /api/v1/categories/{category_id}`

Request body: any subset of `{"name", "type", "is_archived"}`. Response `200`: updated
`CategoryRead`. `404` if not found or not owned by caller. Archiving is one-way — there
is no un-archive path anywhere in the app (a deliberate M2 decision).

## `GET /api/v1/summary`

Query param `month` (`YYYY-MM`, defaults to the current month). Response `200`:
`MonthlySummary` — `total_income`, `total_expense`, `net`, and `by_category` (a
per-category, per-type breakdown for that month).

## `GET /api/v1/budget`

Query param `month` (`YYYY-MM`, defaults to the current month). Response `200`:
`BudgetState` — the caller's `income_target` (manual, nullable), `actual_income_this_month`,
`projected_net` (`income_target - essentials_budget_total - discretionary_budget_total`,
`null` if no income target is set), `actual_net_so_far` (actual income minus **all**
expense transactions for the month, mirroring `GET /api/v1/summary`'s `net` — this can
diverge from `essentials_actual_total + discretionary_actual_total` when untagged
legacy expense data exists), and `lines`: one `BudgetLineRead` per (category, essential/
discretionary) pair that has either a saved budget or any transaction history, each
including `is_archived` (true when the line's category has been archived — the frontend
renders such a line read-only, since un-archiving isn't supported).

## `PUT /api/v1/budget/income-target`

Request body: `{"amount": "3000.00"}`. Response `200`: `IncomeTargetRead`.

## `PUT /api/v1/budget/lines`

Request body: `{"category_id": "uuid", "is_essential": true, "amount": "300.00"}`.
Response `200`: `BudgetLineWriteRead` (`source` is set to `"manual"`). `404` if the
category doesn't exist/isn't owned by the caller/is archived. `422` if the category
isn't an expense category.

## `GET /api/v1/budget/suggestions`

Response `200`: array of `SuggestionItem` (`category_id`, `is_essential`,
`suggested_amount`) — one per currently-eligible (category, essential/discretionary)
line, computed from the last 3 calendar months' totals (3-month weighted average with
outlier trimming). A line is only eligible once all 3 preceding months have at least
one matching transaction.

## `POST /api/v1/budget/lines/accept-suggestion`

Request body: `{"category_id": "uuid", "is_essential": true}`. Response `200`:
`BudgetLineWriteRead` (`source` is set to `"computed"`). `404` if the category doesn't
exist/isn't owned by the caller/is archived. `422` if the category isn't an expense
category, or the line isn't eligible for a suggestion yet.

## `GET /api/v1/health`

Response `200`: `{"status": "ok"}` — unauthenticated, for uptime checks.
