import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt

from app.core.config import get_settings


def _auth_headers_for(user_id: uuid.UUID) -> dict[str, str]:
    """Mint a valid Supabase-style JWT for an arbitrary user_id.

    Mirrors the `auth_headers` fixture in conftest.py but lets a test mint a
    second, independent, valid token for a different user.
    """
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


def test_create_transaction_requires_auth(client, seeded_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "12.50",
            "occurred_on": "2026-09-01",
            "is_essential": True,
        },
    )
    assert response.status_code == 401


def test_create_and_get_transaction(client, auth_headers, seeded_category):
    create_response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "12.50",
            "occurred_on": "2026-09-01",
            "note": "Lunch",
            "is_essential": True,
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["amount"] == "12.50"

    get_response = client.get(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["note"] == "Lunch"


def test_list_transactions_scoped_to_user(client, auth_headers, seeded_category):
    client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    )

    other_user_response = client.get("/api/v1/transactions", headers={"Authorization": "Bearer not-this-users-token"})
    assert other_user_response.status_code == 401

    own_list_response = client.get("/api/v1/transactions", headers=auth_headers)
    assert own_list_response.status_code == 200
    assert len(own_list_response.json()) == 1


def test_update_transaction(client, auth_headers, seeded_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    update_response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"amount": "7.25"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["amount"] == "7.25"


def test_delete_transaction(client, auth_headers, seeded_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    delete_response = client.delete(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 404


def test_create_transaction_rejects_other_users_category(client, auth_headers, other_user_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(other_user_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_update_transaction_rejects_other_users_category(client, auth_headers, seeded_category, other_user_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"category_id": str(other_user_category.id)},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_transactions_are_isolated_between_users(client, auth_headers, seeded_category, other_user_id, other_user_category):
    """Two real, independently-authenticated users must never see or touch each other's data."""
    user_b_headers = _auth_headers_for(other_user_id)

    user_a_transaction = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "note": "User A lunch",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    user_b_transaction = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(other_user_category.id),
            "type": "expense",
            "amount": "99.00",
            "occurred_on": "2026-09-03",
            "note": "User B rent",
            "is_essential": True,
        },
        headers=user_b_headers,
    ).json()

    # User A's list contains only their own transaction, never user B's.
    user_a_list = client.get("/api/v1/transactions", headers=auth_headers)
    assert user_a_list.status_code == 200
    user_a_ids = {item["id"] for item in user_a_list.json()}
    assert user_a_ids == {user_a_transaction["id"]}
    assert user_b_transaction["id"] not in user_a_ids

    # User A cannot fetch, patch, or delete user B's transaction by id (404, not 403 --
    # preserving "don't leak existence" semantics used elsewhere in this file).
    get_response = client.get(f"/api/v1/transactions/{user_b_transaction['id']}", headers=auth_headers)
    assert get_response.status_code == 404

    patch_response = client.patch(
        f"/api/v1/transactions/{user_b_transaction['id']}",
        json={"amount": "1.00"},
        headers=auth_headers,
    )
    assert patch_response.status_code == 404

    delete_response = client.delete(f"/api/v1/transactions/{user_b_transaction['id']}", headers=auth_headers)
    assert delete_response.status_code == 404

    # User B's transaction is untouched and still visible to user B.
    user_b_get = client.get(f"/api/v1/transactions/{user_b_transaction['id']}", headers=user_b_headers)
    assert user_b_get.status_code == 200
    assert user_b_get.json()["amount"] == "99.00"


def test_create_transaction_rejects_type_category_mismatch(client, auth_headers, seeded_category):
    """seeded_category is an expense category; declaring the transaction as income must be rejected."""
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "income",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_transaction_type_alone_rejects_mismatch_with_existing_category(
    client, auth_headers, seeded_category
):
    """Changing only `type` on a transaction must be validated against its current category."""
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"type": "income"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_transaction_category_id_alone_rejects_mismatch_with_existing_type(
    client, auth_headers, seeded_category, seeded_income_category
):
    """Changing only `category_id` on a transaction must be validated against its current type."""
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"category_id": str(seeded_income_category.id)},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_transaction_category_and_type_together_allows_consistent_pair(
    client, auth_headers, seeded_category, seeded_income_category
):
    """Changing category_id and type together to a consistent income pair should succeed."""
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"category_id": str(seeded_income_category.id), "type": "income", "is_essential": None},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["type"] == "income"
    assert response.json()["category_id"] == str(seeded_income_category.id)
    assert response.json()["is_essential"] is None


def test_create_expense_transaction_without_is_essential_is_rejected(client, auth_headers, seeded_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_income_transaction_with_is_essential_is_rejected(client, auth_headers, seeded_income_category):
    response = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_income_category.id),
            "type": "income",
            "amount": "1000.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_can_change_is_essential_alone(client, auth_headers, seeded_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"is_essential": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_essential"] is False


def test_update_cannot_clear_is_essential_on_an_expense_transaction(client, auth_headers, seeded_category):
    created = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "is_essential": True,
        },
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/transactions/{created['id']}",
        json={"is_essential": None},
        headers=auth_headers,
    )
    assert response.status_code == 422
