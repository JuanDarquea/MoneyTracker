from datetime import date


def _three_months_ago_bounds(today: date) -> list[tuple[int, int]]:
    """Return (year, month) for the 3 calendar months before today's month, oldest first.

    Test-only helper: since eligibility is defined relative to the real
    wall-clock date (no `today` override exists in the API, matching how
    summary.py's month defaulting also uses date.today() directly), tests
    compute scenario dates relative to whenever the suite actually runs.
    """
    months = []
    year, month = today.year, today.month
    for _ in range(3):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
        months.append((year, month))
    return list(reversed(months))


def _create_expense(client, headers, category_id, amount, year, month, is_essential):
    return client.post(
        "/api/v1/transactions",
        json={
            "category_id": category_id,
            "type": "expense",
            "amount": amount,
            "occurred_on": f"{year:04d}-{month:02d}-15",
            "is_essential": is_essential,
        },
        headers=headers,
    )


def test_line_with_three_months_of_data_is_eligible_and_suggests_weighted_average(client, auth_headers, seeded_category):
    months = _three_months_ago_bounds(date.today())
    amounts = ["30.00", "60.00", "90.00"]
    for (year, month), amount in zip(months, amounts):
        response = _create_expense(client, auth_headers, str(seeded_category.id), amount, year, month, True)
        assert response.status_code == 201

    suggestions_response = client.get("/api/v1/budget/suggestions", headers=auth_headers)
    assert suggestions_response.status_code == 200
    matching = [
        item for item in suggestions_response.json()
        if item["category_id"] == str(seeded_category.id) and item["is_essential"] is True
    ]
    assert len(matching) == 1
    # 3:2:1 weighting: (3*90 + 2*60 + 1*30) / 6 = 70.00
    assert matching[0]["suggested_amount"] == "70.00"


def test_line_with_gap_month_is_not_eligible(client, auth_headers, seeded_category):
    months = _three_months_ago_bounds(date.today())
    # Only the two most recent of the 3 months have data -- the oldest is missing.
    for (year, month) in months[1:]:
        response = _create_expense(client, auth_headers, str(seeded_category.id), "50.00", year, month, True)
        assert response.status_code == 201

    suggestions_response = client.get("/api/v1/budget/suggestions", headers=auth_headers)
    assert suggestions_response.status_code == 200
    matching = [
        item for item in suggestions_response.json()
        if item["category_id"] == str(seeded_category.id) and item["is_essential"] is True
    ]
    assert matching == []


def test_essential_and_discretionary_lines_are_independently_eligible(client, auth_headers, seeded_category):
    """3 months of essential-only spending shouldn't make the discretionary line of the same category eligible."""
    months = _three_months_ago_bounds(date.today())
    for (year, month) in months:
        _create_expense(client, auth_headers, str(seeded_category.id), "40.00", year, month, True)

    suggestions_response = client.get("/api/v1/budget/suggestions", headers=auth_headers)
    tags = {
        (item["category_id"], item["is_essential"])
        for item in suggestions_response.json()
        if item["category_id"] == str(seeded_category.id)
    }
    assert tags == {(str(seeded_category.id), True)}


def test_accept_suggestion_persists_as_computed(client, auth_headers, seeded_category):
    months = _three_months_ago_bounds(date.today())
    for (year, month) in months:
        _create_expense(client, auth_headers, str(seeded_category.id), "40.00", year, month, False)

    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(seeded_category.id), "is_essential": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == "40.00"
    assert body["source"] == "computed"


def test_accept_suggestion_rejects_ineligible_line(client, auth_headers, seeded_category):
    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(seeded_category.id), "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_accept_suggestion_rejects_other_users_category(client, auth_headers, other_user_category):
    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(other_user_category.id), "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_accept_suggestion_rejects_income_category(client, auth_headers, seeded_income_category):
    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(seeded_income_category.id), "is_essential": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_suggestions_requires_auth(client):
    response = client.get("/api/v1/budget/suggestions")
    assert response.status_code == 401


def test_accept_suggestion_requires_auth(client, seeded_category):
    response = client.post(
        "/api/v1/budget/lines/accept-suggestion",
        json={"category_id": str(seeded_category.id), "is_essential": True},
    )
    assert response.status_code == 401
