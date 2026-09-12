from decimal import Decimal


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
