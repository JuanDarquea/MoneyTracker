import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt

from app.core.config import get_settings
from app.services import budget as budget_service


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


def test_income_target_requires_auth(client):
    response = client.put("/api/v1/budget/income-target", json={"amount": "3000.00"})
    assert response.status_code == 401


def test_set_income_target_creates_then_updates(client, auth_headers):
    create_response = client.put(
        "/api/v1/budget/income-target", json={"amount": "3000.00"}, headers=auth_headers
    )
    assert create_response.status_code == 200
    assert create_response.json()["amount"] == "3000.00"

    update_response = client.put(
        "/api/v1/budget/income-target", json={"amount": "3200.00"}, headers=auth_headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["amount"] == "3200.00"


def test_income_target_rejects_non_positive_amount(client, auth_headers):
    response = client.put("/api/v1/budget/income-target", json={"amount": "0.00"}, headers=auth_headers)
    assert response.status_code == 422


def test_income_target_isolated_between_users(client, auth_headers, user_id, other_user_id, db):
    client.put("/api/v1/budget/income-target", json={"amount": "3000.00"}, headers=auth_headers)

    assert budget_service.get_income_target(db, other_user_id) is None
    own_target = budget_service.get_income_target(db, user_id)
    assert own_target is not None
    assert own_target.amount == Decimal("3000.00")


def test_set_budget_line_requires_auth(client, seeded_category):
    response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
    )
    assert response.status_code == 401


def test_set_budget_line_creates_then_updates_as_manual(client, auth_headers, seeded_category):
    create_response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    body = create_response.json()
    assert body["amount"] == "300.00"
    assert body["source"] == "manual"

    update_response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "350.00"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["amount"] == "350.00"


def test_set_budget_line_essential_and_discretionary_are_independent_lines(client, auth_headers, seeded_category):
    essential_response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "300.00"},
        headers=auth_headers,
    )
    discretionary_response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": False, "amount": "100.00"},
        headers=auth_headers,
    )
    assert essential_response.json()["amount"] == "300.00"
    assert discretionary_response.json()["amount"] == "100.00"


def test_set_budget_line_rejects_income_category(client, auth_headers, seeded_income_category):
    response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_income_category.id), "is_essential": True, "amount": "100.00"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_set_budget_line_rejects_other_users_category(client, auth_headers, other_user_category):
    response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(other_user_category.id), "is_essential": True, "amount": "100.00"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_set_budget_line_rejects_archived_category(client, auth_headers, seeded_category):
    client.patch(
        f"/api/v1/categories/{seeded_category.id}",
        json={"is_archived": True},
        headers=auth_headers,
    )
    response = client.put(
        "/api/v1/budget/lines",
        json={"category_id": str(seeded_category.id), "is_essential": True, "amount": "100.00"},
        headers=auth_headers,
    )
    assert response.status_code == 404
