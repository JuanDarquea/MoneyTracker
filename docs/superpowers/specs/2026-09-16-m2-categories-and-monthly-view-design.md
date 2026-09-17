# M2 — Categories & Monthly View — Design

**Builds on:** M1 (skateboard) — auth + transaction CRUD, live on Render +
Supabase. `Planning/02_agent_structure.md`'s milestone table scopes M2 as
"Category CRUD, monthly summary endpoint" (backend) / "Category management
UI, monthly dashboard" (frontend).

**Status:** Approved design, ready for implementation planning.

---

## Problem

M1 shipped with categories as a **global**, read-only, seeded list (7 rows,
no owner) — fine while nothing wrote to that table. M2 adds category
*creation*, which forces categories to become a real per-user resource, plus
a monthly aggregation view over a user's transactions. Today:

- There's no way for a user to create, rename, or remove a category.
- There's no way to see monthly totals or a category breakdown — the app
  can only add one transaction at a time with no feedback on the bigger
  picture.
- The Flutter app has no navigation beyond a single screen (`TransactionEntryScreen`
  right after login) — nothing to move between yet, because M1 only had
  one screen.

## Scope decisions (confirmed)

1. **Categories are per-user, not global.** Each user has their own list;
   nothing is shared across users.
2. **Categories are archived, never hard-deleted.** A user "removing" a
   category always sets `is_archived = true`. This preserves referential
   integrity for existing transactions and matches the outline's explicit
   goal (`01_project_outline.md` §8, flow 5): "archive categories at any
   time without breaking historical data integrity."
3. **Monthly summary is single-month only** (totals + category breakdown
   for one calendar month, `?month=` query param, default current month).
   No month-over-month or 3-month-average comparison in M2 — that overlaps
   with the budget engine's rolling-average logic, which is explicitly M3
   scope (`02_agent_structure.md` milestone table: "Budget suggestion
   endpoint (3-month engine)"). Building it now would mean redoing it once
   M3's essential/discretionary-aware engine exists.

## Data model changes

`categories` (currently: `id`, `name`, `type`, `is_essential`) gains:

- `user_id UUID NOT NULL` — same ownership pattern as `transactions.user_id`
  (no FK to Supabase's `auth.users`; that table isn't ours to reference).
- `is_archived BOOLEAN NOT NULL DEFAULT false`

### Migration and existing data

The 7 categories seeded in M1 have no owner, and are referenced by the 2
transactions created while manually verifying M1/the Render deploy. All of
that is pre-launch smoke-test data, not real user data. The migration:

1. Deletes the 2 existing transactions (they reference categories that are
   about to lose their meaning as "the shared defaults").
2. Deletes the 7 existing seeded categories.
3. Adds `user_id` (`NOT NULL`) and `is_archived` (`NOT NULL DEFAULT false`)
   to `categories`.

No replacement seed data ships in the migration. Instead, **the backend
lazily creates the 7 starter categories for a user the first time it needs
their category list and finds none** (`GET /api/v1/categories`, and any
other endpoint that needs to resolve "this user's categories" first). This
requires no Supabase Auth signup webhook or hook — it reuses the same
"verify JWT, act for that specific user" pattern every endpoint already
follows. The seed step must be idempotent (safe to no-op if the user
already has categories, even under concurrent requests — a unique
constraint or a simple existence check before insert is enough given this
app's traffic scale).

## Backend API

### Categories — `app/api/v1/categories.py`

- `GET /api/v1/categories` — ensures the 7 starter categories exist for the
  caller (lazy-seed), then returns their categories. `?include_archived=true`
  includes archived ones (needed later for resolving category names on old
  transactions); default excludes them.
- `POST /api/v1/categories` — create. Body: `name` (1-64 chars), `type`
  (`income`/`expense`), `is_essential` (optional `bool`). `is_essential`
  is rejected (422) if provided with `type=income` — the field only makes
  sense for expense categories.
- `PATCH /api/v1/categories/{id}` — update `name` and/or `is_essential`,
  or archive via `{"is_archived": true}`. 404 if the category doesn't
  exist or isn't owned by the caller. No route accepts un-archiving in
  this milestone (not asked for; can be added later if needed).
- No `DELETE /api/v1/categories/{id}` route. Per the archive-only decision,
  a `DELETE` that doesn't delete would be a confusing contract — archiving
  goes through `PATCH`.

Service layer: `app/services/categories.py` — `ensure_default_categories(db, user_id)`,
`list_categories(db, user_id, include_archived)`, `create_category`,
`update_category`, `get_category`.

### Cross-cutting fix: transaction category ownership

`app/services/transactions.py` (`create_transaction`, `update_transaction`)
must validate that `category_id` belongs to the requesting user. Under M1's
global categories this check was meaningless (everything belonged to
everyone); under per-user categories, skipping it lets user A create a
transaction against user B's category. This is a genuine bug being fixed
here, not new scope — needs a regression test asserting the rejection
(404 or 400, consistent with how the rest of the API reports
not-found-or-not-yours).

### Monthly summary — `app/api/v1/summary.py`

- `GET /api/v1/summary?month=YYYY-MM` (defaults to the current month).
  Auth-protected, scoped to the caller. Response:

  ```json
  {
    "month": "2026-09",
    "total_income": "0.00",
    "total_expense": "0.00",
    "net": "0.00",
    "by_category": [
      {"category_id": "...", "category_name": "Food", "type": "expense", "amount": "0.00"}
    ]
  }
  ```

- Pure read-only aggregation (SQL `GROUP BY` over the caller's
  transactions for that month) — no new table, no service beyond a query
  function. `Decimal`-safe throughout (`Numeric` columns, never floats).
  Empty month (no transactions) returns zeroed totals and an empty
  `by_category` list, not a 404.

Service layer: `app/services/summary.py` — `get_monthly_summary(db, user_id, month)`.
Schema: `app/schemas/summary.py` — `MonthlySummary`, `CategoryBreakdownItem`.

## Frontend

### Navigation shell (new)

M1 went straight from login to `TransactionEntryScreen` — the only screen
that existed. M2 adds two more, so login now lands on a 3-tab bottom
navigation: **Dashboard / Add / Categories**. This replaces the
direct-to-entry-screen redirect in `LoginScreen`.

### `lib/features/categories/`

- `models/category.dart` — `Category { id, name, type, isEssential, isArchived }`
- `providers/category_provider.dart` — Riverpod provider wrapping the 3
  category endpoints
- `screens/category_list_screen.dart` — list, essential/discretionary
  toggle per expense category, "Archive" action, "+ New category" entry
  point
- `screens/category_form_screen.dart` — create/edit form: name,
  income/expense toggle, essential toggle (shown only when type=expense)

### `lib/features/dashboard/`

- `models/monthly_summary.dart`
- `providers/dashboard_provider.dart` — fetches the summary for a given
  month (defaults to current)
- `screens/dashboard_screen.dart` — income/expense/net totals + category
  breakdown as a simple list with proportional bar widths. No new charting
  dependency (e.g. `fl_chart`) — a real chart is a later polish pass, not
  needed to satisfy M2's "breakdown by category" requirement.

### Closing the M1 placeholder

`TransactionEntryScreen`'s hardcoded `_placeholderCategories` map is
replaced with a real fetch from `GET /api/v1/categories`, filtered to the
current Expense/Income toggle state.

## Testing

**Backend** (pytest, local Docker Postgres — same pattern as M1, no live
Supabase dependency):

- Lazy-seed creates exactly the 7 starter categories on first access;
  idempotent on a second call.
- Category create/update/archive; archived categories excluded from the
  default list but still resolve correctly when referenced by old
  transactions.
- Cross-user isolation: user A cannot see, update, or archive user B's
  categories.
- `is_essential` rejected when `type=income`.
- Regression test: creating/updating a transaction with another user's
  `category_id` is rejected.
- Summary: empty month → zeroed totals, empty breakdown; single and
  multiple transactions aggregate correctly; `Decimal` precision preserved;
  cross-user isolation; omitted `month` defaults to the current month.

**Frontend** (`flutter test`, no network — fakes/provider overrides, same
pattern as M1):

- `CategoryListScreen` / `CategoryFormScreen`: smoke-level widget tests
  (list renders, essential toggle only appears for expense, form validates
  required fields).
- `DashboardScreen`: renders totals and breakdown from a fake summary
  response.
- `TransactionEntryScreen`: existing test updated for the category source
  moving from the hardcoded map to the (faked) provider.

**Manual click-through** (in addition to automated tests, not instead of):
after each major feature lands — category CRUD, the transaction
ownership fix, the summary endpoint, the dashboard screen, the category
screens — click through it live in the browser (real login, real backend,
real Supabase project) before moving to the next feature, the same way M1
and the Render deploy were verified. Automated tests prove the logic;
clicking through proves the feature actually works end to end for a real
user. Catches integration issues automated tests miss — the Render
`SUPABASE_URL` bug during M1 verification is a concrete example of a class
of bug this step catches and pure unit/API tests don't.

## Out of scope for M2

- Month-over-month / 3-month-average comparisons (M3, budget engine).
- Un-archiving a category.
- Any charting library / visual chart component.
- Editing/deleting past transactions from a history view (no history/list
  screen exists yet — M1 only ever built the entry form; a transactions
  list view isn't in this milestone's deliverables per the milestone table
  and isn't required to satisfy "monthly dashboard").
