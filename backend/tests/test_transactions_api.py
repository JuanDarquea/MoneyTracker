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
        },
        headers=auth_headers,
    ).json()

    delete_response = client.delete(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/transactions/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 404


def test_transactions_are_isolated_between_users(client, auth_headers, seeded_category):
    """Two real, independently-authenticated users must never see or touch each other's data."""
    user_b_headers = _auth_headers_for(uuid.uuid4())

    user_a_transaction = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "5.00",
            "occurred_on": "2026-09-02",
            "note": "User A lunch",
        },
        headers=auth_headers,
    ).json()

    user_b_transaction = client.post(
        "/api/v1/transactions",
        json={
            "category_id": str(seeded_category.id),
            "type": "expense",
            "amount": "99.00",
            "occurred_on": "2026-09-03",
            "note": "User B rent",
        },
        headers=user_b_headers,
    ).json()

    # User A's list contains only their own transaction, never user B's.
    user_a_list = client.get("/api/v1/transactions", headers=auth_headers)
    assert user_a_list.status_code == 200
    user_a_ids = {item["id"] for item in user_a_list.json()}
    assert user_a_ids == {user_a_transaction["id"]}
    assert user_b_transaction["id"] not in user_a_ids

    # User A cannot fetch, patch, or delete user B's transaction by id (404, not 403 —
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
