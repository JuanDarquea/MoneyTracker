# MoneyTracker API Contract — M1

Machine-readable schema: `docs/api/openapi.json` (regenerate with
`python backend/scripts/export_openapi.py` any time endpoints change).

## Auth

Every endpoint below requires `Authorization: Bearer <supabase-jwt>`.
Missing/invalid/expired token → `401`.

## `POST /api/v1/transactions`

Request body:
```json
{
  "category_id": "uuid",
  "type": "income | expense",
  "amount": "12.50",
  "occurred_on": "2026-09-01",
  "note": "optional string, max 280 chars"
}
```
`amount` is a decimal string, positive, at most 2 decimal places.
Response `201`: `TransactionRead` (adds `id`, `user_id`, `created_at`, `updated_at`).

## `GET /api/v1/transactions`

Response `200`: array of `TransactionRead`, scoped to the caller, newest `occurred_on` first.

## `GET /api/v1/transactions/{id}`

Response `200`: `TransactionRead`. `404` if not found or not owned by caller.

## `PATCH /api/v1/transactions/{id}`

Request body: any subset of the `POST` fields. Response `200`: updated `TransactionRead`.

## `DELETE /api/v1/transactions/{id}`

Response `204`.

## `GET /api/v1/health`

Response `200`: `{"status": "ok"}` — unauthenticated, for uptime checks.

## Not in this contract yet (M2+)

Category CRUD, monthly summary, budget suggestion endpoints — see
`Planning/02_agent_structure.md` milestone table.
