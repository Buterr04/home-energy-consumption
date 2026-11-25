from fastapi.testclient import TestClient


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_authentication_and_ownership(
    client: TestClient, demo_token: str
) -> None:
    me = client.get("/api/v1/auth/me", headers=auth_headers(demo_token))
    assert me.status_code == 200
    assert me.json()["username"] == "demo1"

    invalid = client.post(
        "/api/v1/auth/login",
        json={"username": "demo1", "password": "wrong"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["detail"]["code"] == "AUTH_INVALID_CREDENTIALS"

    households = client.get(
        "/api/v1/households", headers=auth_headers(demo_token)
    )
    assert households.status_code == 200
    assert [item["household_id"] for item in households.json()["items"]] == [1, 2]
    assert "owner_user_id" not in households.json()["items"][0]

    forbidden = client.get(
        "/api/v1/households/3", headers=auth_headers(demo_token)
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "FORBIDDEN_HOUSEHOLD"


def test_consumption_series_and_validation(
    client: TestClient, demo_token: str
) -> None:
    response = client.get(
        "/api/v1/consumption/series",
        params=[("household_ids", 1), ("household_ids", 2)],
        headers=auth_headers(demo_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["granularity"] == "day"
    assert len(body["items"]) >= 2
    assert set(body["meta"]) == {
        "unit",
        "max_households",
        "excluded_appliance_ids",
    }

    too_many = client.get(
        "/api/v1/consumption/series",
        params=[("household_ids", value) for value in range(1, 7)],
        headers=auth_headers(demo_token),
    )
    assert too_many.status_code == 400
    assert too_many.json()["detail"]["code"] == "TOO_MANY_HOUSEHOLDS"

    filters = client.get(
        "/api/v1/consumption/series",
        params=[
            ("household_ids", 1),
            ("include_appliance_ids", 1),
            ("exclude_appliance_ids", 2),
        ],
        headers=auth_headers(demo_token),
    )
    assert filters.status_code == 400
    assert filters.json()["detail"]["code"] == "INVALID_APPLIANCE_FILTER"

    invalid_dates = client.get(
        "/api/v1/consumption/series",
        params={
            "household_ids": 1,
            "start_date": "2023-12-10",
            "end_date": "2023-12-01",
        },
        headers=auth_headers(demo_token),
    )
    assert invalid_dates.status_code == 400
    assert invalid_dates.json()["detail"]["code"] == "INVALID_DATE_RANGE"


def test_average_breakdown_and_report(
    client: TestClient, demo_token: str
) -> None:
    average = client.get(
        "/api/v1/consumption/average",
        headers=auth_headers(demo_token),
    )
    assert average.status_code == 200
    assert average.json()["items"]
    assert average.json()["items"][0]["expected_households"] == 3
    assert set(average.json()["meta"]) == {
        "unit",
        "excluded_appliance_ids",
    }

    breakdown = client.get(
        "/api/v1/consumption/breakdown",
        params={"household_id": 1},
        headers=auth_headers(demo_token),
    )
    assert breakdown.status_code == 200
    assert breakdown.json()["total_kwh"] > 0
    assert len(breakdown.json()["items"]) == 2

    appliances = client.get(
        "/api/v1/appliances", headers=auth_headers(demo_token)
    )
    assert appliances.status_code == 200
    assert len(appliances.json()["items"]) == 2

    report = client.get(
        "/api/v1/reports/summary",
        params=[
            ("household_ids", 1),
            ("household_ids", 2),
            ("granularity", "month"),
            ("format", "csv"),
        ],
        headers=auth_headers(demo_token),
    )
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/csv")
    assert report.text.splitlines()[0].startswith("household_id,period")
    assert ",3.0," not in report.text


def test_model_info_and_prediction(
    client: TestClient, demo_token: str
) -> None:
    info = client.get(
        "/api/v1/ai/model", headers=auth_headers(demo_token)
    )
    assert info.status_code == 200
    assert info.json()["version"] == "test-rf"

    prediction = client.post(
        "/api/v1/ai/predict",
        json={"household_id": 1, "month": 12, "household_size": 3},
        headers=auth_headers(demo_token),
    )
    assert prediction.status_code == 200
    assert prediction.json()["predicted_avg_daily_kwh"] >= 0

    invalid = client.post(
        "/api/v1/ai/predict",
        json={"household_id": 1, "month": 13, "household_size": 3},
        headers=auth_headers(demo_token),
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "INVALID_MONTH"

    batch = client.post(
        "/api/v1/ai/predict/batch",
        json={
            "items": [
                {"household_id": 1, "month": 1, "household_size": 3},
                {"household_id": 1, "month": 7, "household_size": 3},
            ]
        },
        headers=auth_headers(demo_token),
    )
    assert batch.status_code == 200
    assert set(batch.json()["items"][0]) == {
        "household_id",
        "month",
        "predicted_avg_daily_kwh",
    }


def test_admin_management(
    client: TestClient, admin_token: str
) -> None:
    created = client.post(
        "/api/v1/admin/users",
        json={
            "username": "pytest_user",
            "password": "pytest123",
            "display_name": "Pytest User",
            "role": "user",
        },
        headers=auth_headers(admin_token),
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    assigned = client.post(
        f"/api/v1/admin/users/{user_id}/households",
        json={"household_ids": [1, 2]},
        headers=auth_headers(admin_token),
    )
    assert assigned.status_code == 200
    assert assigned.json()["owned"] == [1, 2]

    users = client.get(
        "/api/v1/admin/users", headers=auth_headers(admin_token)
    )
    assert users.status_code == 200
    assert any(item["username"] == "pytest_user" for item in users.json()["items"])

    all_households = client.get(
        "/api/v1/households", headers=auth_headers(admin_token)
    )
    assert all_households.status_code == 200
    assert "owner_user_id" not in all_households.json()["items"][0]

    admin_households = client.get(
        "/api/v1/admin/households", headers=auth_headers(admin_token)
    )
    assert admin_households.status_code == 200
    assert "owner_user_id" in admin_households.json()["items"][0]


def test_admin_csv_import_and_history(
    client: TestClient, admin_token: str
) -> None:
    csv_content = (
        "Home ID,Appliance Type,Energy Consumption (kWh),Time,Date,"
        "Outdoor Temperature (°C),Season,Household Size\n"
        "1,Fridge,1.1,12:00,2023-12-03,4.0,Winter,3\n"
    )
    imported = client.post(
        "/api/v1/admin/imports",
        files={"file": ("api-import.csv", csv_content, "text/csv")},
        headers=auth_headers(admin_token),
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["import_id"] > 0
    assert body["status"] == "completed"
    assert body["inserted_rows"] == 1

    history = client.get(
        "/api/v1/admin/imports",
        headers=auth_headers(admin_token),
    )
    assert history.status_code == 200
    assert any(
        item["import_id"] == body["import_id"]
        for item in history.json()["items"]
    )

