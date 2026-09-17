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


def test_summary_for_empty_month_returns_zeroed_totals(client, auth_headers):
    response = client.get("/api/v1/summary?month=2020-01", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2020-01"
    assert body["total_income"] == "0.00"
    assert body["total_expense"] == "0.00"
    assert body["net"] == "0.00"
    assert body["by_category"] == []


def test_summary_aggregates_by_category_and_type(client, auth_headers, seeded_category, seeded_income_category):
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "20.00", "occurred_on": "2026-09-05"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "15.50", "occurred_on": "2026-09-10"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_income_category.id), "type": "income", "amount": "1000.00", "occurred_on": "2026-09-01"},
        headers=auth_headers,
    )
    # Outside the queried month -- must not be included.
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "999.00", "occurred_on": "2026-08-15"},
        headers=auth_headers,
    )

    response = client.get("/api/v1/summary?month=2026-09", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_income"] == "1000.00"
    assert body["total_expense"] == "35.50"
    assert body["net"] == "964.50"

    by_category = {item["category_name"]: item["amount"] for item in body["by_category"]}
    assert by_category["Food"] == "35.50"
    assert by_category["Salary"] == "1000.00"


def test_summary_defaults_to_current_month(client, auth_headers, seeded_category):
    from datetime import date

    today = date.today().isoformat()
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "10.00", "occurred_on": today},
        headers=auth_headers,
    )

    response = client.get("/api/v1/summary", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total_expense"] == "10.00"


def test_summary_rejects_invalid_month_value(client, auth_headers):
    response = client.get("/api/v1/summary?month=2026-13", headers=auth_headers)
    assert response.status_code == 422

    response = client.get("/api/v1/summary?month=2026-00", headers=auth_headers)
    assert response.status_code == 422


def test_summary_is_isolated_between_users(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={"category_id": str(seeded_category.id), "type": "expense", "amount": "50.00", "occurred_on": "2026-09-05"},
        headers=auth_headers,
    )

    other_headers = _auth_headers_for(uuid.uuid4())
    response = client.get("/api/v1/summary?month=2026-09", headers=other_headers)
    assert response.status_code == 200
    assert response.json()["total_expense"] == "0.00"
