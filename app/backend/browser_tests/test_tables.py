"""The table browser works even when unrelated ORM relationships are invalid."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db import database, models
from routers.tables import router


@pytest.fixture

def browser():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(models.User.__table__.insert(), [
            {"full_name": "Marine Researcher", "email": "marine@example.org", "password": "private-hash"},
            {"full_name": "Field Researcher", "email": "field@example.org", "password": "another-hash"},
        ])
    app = FastAPI()
    app.include_router(router)

    def get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database.get_db] = get_db
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_catalog_has_all_application_tables_and_counts(browser):
    response = browser.get("/tables/")
    assert response.status_code == 200
    entries = {item["name"]: item for item in response.json()["tables"]}
    assert set(entries) == set(database.Base.metadata.tables)
    assert entries["users"]["count"] == 2
    assert entries["observations"]["count"] == 0


def test_catalog_sorted_by_survey_workflow_and_relation_dependency(browser):
    response = browser.get("/tables/")
    assert response.status_code == 200
    table_names = [item["name"] for item in response.json()["tables"]]
    survey_order = [
        "projects",
        "fieldtrips",
        "day_sheets",
        "calibrations",
        "deployments",
        "analysis_periods",
        "observations",
        "measurements",
    ]
    # Filter catalog tables down to survey tables and verify order matches exactly
    catalog_survey_tables = [name for name in table_names if name in survey_order]
    assert catalog_survey_tables == survey_order


def test_records_hide_passwords_and_paginate(browser):
    response = browser.get("/tables/users?limit=1&skip=1")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 2
    assert len(result["items"]) == 1
    assert result["items"][0]["email"] == "field@example.org"
    assert "password" not in result["items"][0]
    assert "password" not in {column["name"] for column in result["columns"]}


def test_search_and_empty_table(browser):
    result = browser.get("/tables/users?search=Marine").json()
    assert result["total"] == 1
    assert result["items"][0]["full_name"] == "Marine Researcher"
    assert browser.get("/tables/users?search=%25").json()["total"] == 0
    empty = browser.get("/tables/projects").json()
    assert empty["total"] == 0
    assert empty["items"] == []
    assert empty["columns"]


def test_unknown_tables_and_invalid_pagination_are_rejected(browser):
    assert browser.get("/tables/alembic_version").status_code == 404
    assert browser.get("/tables/users?skip=-1").status_code == 422
    assert browser.get("/tables/users?limit=1000").status_code == 422


def test_download_table_records_csv_and_xlsx(browser):
    # CSV download
    csv_resp = browser.get("/tables/users/download?format=csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert 'filename="users_records.csv"' in csv_resp.headers["content-disposition"]
    content = csv_resp.content.decode("utf-8-sig")
    assert "marine@example.org" in content
    assert "field@example.org" in content
    assert "password" not in content

    # Excel download
    xlsx_resp = browser.get("/tables/users/download?format=xlsx")
    assert xlsx_resp.status_code == 200
    assert "openxmlformats-officedocument" in xlsx_resp.headers["content-type"]
    assert 'filename="users_records.xlsx"' in xlsx_resp.headers["content-disposition"]

    # Filtered download with search
    filtered_resp = browser.get("/tables/users/download?format=csv&search=Marine")
    assert filtered_resp.status_code == 200
    f_content = filtered_resp.content.decode("utf-8-sig")
    assert "marine@example.org" in f_content
    assert "field@example.org" not in f_content


def test_download_selected_table_records_csv_and_xlsx(browser):
    users_data = browser.get("/tables/users").json()
    items = users_data["items"]
    assert len(items) >= 2
    id1 = items[0]["id"]
    id2 = items[1]["id"]
    email1 = items[0]["email"]
    email2 = items[1]["email"]

    # 1. Download single selected record via GET comma-separated ids
    resp = browser.get(f"/tables/users/download?format=csv&ids={id1}")
    assert resp.status_code == 200
    assert 'filename="users_selected_records.csv"' in resp.headers["content-disposition"]
    content = resp.content.decode("utf-8-sig")
    assert email1 in content
    assert email2 not in content

    # 2. Download multiple selected records via GET repeated query params
    resp2 = browser.get(f"/tables/users/download?format=csv&ids={id1}&ids={id2}")
    assert resp2.status_code == 200
    assert 'filename="users_selected_records.csv"' in resp2.headers["content-disposition"]
    content2 = resp2.content.decode("utf-8-sig")
    assert email1 in content2
    assert email2 in content2

    # 3. Download selected records via POST JSON
    post_resp = browser.post("/tables/users/download", json={"ids": [id2], "format": "xlsx"})
    assert post_resp.status_code == 200
    assert "openxmlformats-officedocument" in post_resp.headers["content-type"]
    assert 'filename="users_selected_records.xlsx"' in post_resp.headers["content-disposition"]

    # 4. Error on invalid id format
    bad_resp = browser.get("/tables/users/download?ids=invalid,xyz")
    assert bad_resp.status_code == 400
