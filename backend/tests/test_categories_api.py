import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

DEFAULT_CATEGORY_NAMES = {"Salary", "Food", "Transport", "Housing", "Utilities", "Entertainment", "Shopping"}


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


def test_list_categories_lazily_seeds_defaults(client, auth_headers):
    response = client.get("/api/v1/categories", headers=auth_headers)
    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == DEFAULT_CATEGORY_NAMES


def test_list_categories_lazy_seed_is_idempotent(client, auth_headers):
    client.get("/api/v1/categories", headers=auth_headers)
    second_response = client.get("/api/v1/categories", headers=auth_headers)
    assert len(second_response.json()) == 7


def test_create_category(client, auth_headers):
    response = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense", "is_essential": False},
        headers=auth_headers,
    )
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Gym"
    assert created["is_archived"] is False


def test_create_category_rejects_is_essential_on_income(client, auth_headers):
    response = client.post(
        "/api/v1/categories",
        json={"name": "Freelance", "type": "income", "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_update_category_name_and_essential(client, auth_headers):
    created = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense", "is_essential": False},
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/categories/{created['id']}",
        json={"name": "Gym Membership", "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Gym Membership"
    assert response.json()["is_essential"] is True


def test_update_category_rejects_is_essential_on_income(client, auth_headers):
    created = client.post(
        "/api/v1/categories",
        json={"name": "Freelance", "type": "income"},
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/categories/{created['id']}",
        json={"is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_archive_category_hides_it_from_default_list(client, auth_headers):
    created = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense"},
        headers=auth_headers,
    ).json()

    archive_response = client.patch(
        f"/api/v1/categories/{created['id']}",
        json={"is_archived": True},
        headers=auth_headers,
    )
    assert archive_response.status_code == 200

    default_list = client.get("/api/v1/categories", headers=auth_headers)
    assert created["id"] not in {item["id"] for item in default_list.json()}

    full_list = client.get("/api/v1/categories?include_archived=true", headers=auth_headers)
    assert created["id"] in {item["id"] for item in full_list.json()}


def test_categories_are_isolated_between_users(client, auth_headers):
    user_a_category = client.post(
        "/api/v1/categories",
        json={"name": "Gym", "type": "expense"},
        headers=auth_headers,
    ).json()

    user_b_headers = _auth_headers_for(uuid.uuid4())
    user_b_list = client.get("/api/v1/categories", headers=user_b_headers).json()

    assert user_a_category["id"] not in {item["id"] for item in user_b_list}
    assert {item["name"] for item in user_b_list} == DEFAULT_CATEGORY_NAMES

    patch_response = client.patch(
        f"/api/v1/categories/{user_a_category['id']}",
        json={"name": "Hijacked"},
        headers=user_b_headers,
    )
    assert patch_response.status_code == 404
