import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import jwt

from app.core.config import get_settings
from app.models import Transaction, TransactionType


def _auth_headers_for(user_id: uuid.UUID) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": settings.supabase_jwt_aud,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_budget_requires_auth(client):
    response = client.get("/api/v1/budget")
    assert response.status_code == 401


def test_budget_empty_state_has_no_income_target_and_no_lines(client, auth_headers):
    response = client.get("/api/v1/budget?month=2020-01", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["income_target"] is None
    assert body["projected_net"] is None
    assert body["lines"] == []
    assert body["actual_income_this_month"] == "0.00"
    assert body["actual_net_so_far"] == "0.00"


def test_budget_rejects_invalid_month(client, auth_headers):
    response = client.get("/api/v1/budget?month=2026-13", headers=auth_headers)
    assert response.status_code == 422


def test_budget_line_appears_from_history_without_a_saved_budget(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "40.00",
            "occurred_on": "2026-09-05",
            "is_essential": True,
        },
        headers=auth_headers,
    )

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    assert response.status_code == 200
    lines = response.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["category_id"] == str(seeded_category.id)
    assert lines[0]["is_essential"] is True
    assert lines[0]["budget_amount"] is None
    assert lines[0]["source"] is None
    assert lines[0]["actual_this_month"] == "40.00"


def test_budget_totals_and_projected_net(client, auth_headers, seeded_category):
    client.put("/api/v1/budget/income-target", json={"amount": "3000.00"}, headers=auth_headers)
    client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
        headers=auth_headers,
    )
    client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": False, "amount": "100.00"},
        headers=auth_headers,
    )

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    body = response.json()
    assert body["income_target"] == "3000.00"
    assert body["essentials_budget_total"] == "300.00"
    assert body["discretionary_budget_total"] == "100.00"
    assert body["projected_net"] == "2600.00"


def test_budget_actual_net_so_far(client, auth_headers, seeded_category, seeded_income_category):
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_income_category.id), "type": "income", "amount": "1000.00", "occurred_on": "2026-09-01"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "150.00", "occurred_on": "2026-09-05", "is_essential": True},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "50.00", "occurred_on": "2026-09-10", "is_essential": False},
        headers=auth_headers,
    )

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    body = response.json()
    assert body["actual_income_this_month"] == "1000.00"
    assert body["essentials_actual_total"] == "150.00"
    assert body["discretionary_actual_total"] == "50.00"
    assert body["actual_net_so_far"] == "800.00"


def test_budget_month_query_param_scopes_actuals_but_not_line_presence(client, auth_headers, seeded_category):
    """A line's presence depends on all-time history; only its actual_this_month is month-scoped."""
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "40.00", "occurred_on": "2026-08-05", "is_essential": True},
        headers=auth_headers,
    )

    september_response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    september_lines = september_response.json()["lines"]
    assert len(september_lines) == 1
    assert september_lines[0]["actual_this_month"] == "0.00"

    august_response = client.get("/api/v1/budget?month=2026-08", headers=auth_headers)
    august_lines = august_response.json()["lines"]
    assert len(august_lines) == 1
    assert august_lines[0]["actual_this_month"] == "40.00"


def test_budget_actual_net_so_far_includes_untagged_legacy_expenses(
    client, auth_headers, seeded_category, seeded_income_category, user_id, db
):
    """A pre-M3/backfilled transaction with is_essential=NULL is invisible to the
    essentials/discretionary totals (they're scoped to tagged data by design), but
    actual_net_so_far must still reflect it -- mirroring summary.py's `net`.

    Expense validation via the API rejects a missing is_essential tag (Task 1), so
    the untagged row is inserted directly via the db session, the same way
    test_models.py constructs transactions directly, to simulate legacy/backfilled
    data.
    """
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_income_category.id),
            "type": "income",
            "amount": "1000.00",
            "occurred_on": "2026-09-01",
        },
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "150.00",
            "occurred_on": "2026-09-05",
            "is_essential": True,
        },
        headers=auth_headers,
    )
    untagged_txn = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        category_id=seeded_category.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("75.00"),
        occurred_on=date(2026, 9, 10),
        is_essential=None,
    )
    db.add(untagged_txn)
    db.commit()

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    # actual_net_so_far reflects both the tagged (150.00) and untagged (75.00)
    # expenses: 1000.00 - 150.00 - 75.00 = 775.00.
    assert body["actual_net_so_far"] == "775.00"
    # essentials_actual_total only reflects tagged data -- the untagged 75.00
    # never appears in either bucket, which is why the two figures diverge.
    assert body["essentials_actual_total"] == "150.00"
    assert body["discretionary_actual_total"] == "0.00"


def test_budget_line_reports_is_archived_for_archived_category(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "40.00",
            "occurred_on": "2026-09-05",
            "is_essential": True,
        },
        headers=auth_headers,
    )
    archive_response = client.patch(
        f"/api/v1/categories/{seeded_category.id}",
        json={"is_archived": True},
        headers=auth_headers,
    )
    assert archive_response.status_code == 200

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    assert response.status_code == 200
    lines = response.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["is_archived"] is True


def test_budget_line_reports_not_archived_for_active_category(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "40.00",
            "occurred_on": "2026-09-05",
            "is_essential": True,
        },
        headers=auth_headers,
    )

    response = client.get("/api/v1/budget?month=2026-09", headers=auth_headers)
    lines = response.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["is_archived"] is False


def test_budget_is_isolated_between_users(client, auth_headers, seeded_category, other_user_id):
    client.put("/api/v1/budget/income-target", json={"amount": "3000.00"}, headers=auth_headers)
    client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
        headers=auth_headers,
    )

    other_headers = _auth_headers_for(other_user_id)
    response = client.get("/api/v1/budget", headers=other_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["income_target"] is None
    assert body["lines"] == []
