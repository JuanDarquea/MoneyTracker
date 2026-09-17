import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings


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
