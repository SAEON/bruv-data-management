"""Data entry integration checks use an isolated database, never the configured server."""

import csv
import io
import json
from datetime import date, time

import bcrypt
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db import database, models
from routers import tables, upload


@pytest.fixture
def entry():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    database.Base.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(upload.router)
    app.include_router(tables.router)

    def get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database.get_db] = get_db
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def spreadsheet(rows, format="csv", sheets=None):
    output = io.BytesIO()
    if format == "csv":
        output.write(pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"))
    else:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for name, data in (sheets or {"Data": rows}).items():
                pd.DataFrame(data).to_excel(writer, sheet_name=name, index=False)
    return ("records." + format, output.getvalue())


def bulk(client, endpoint, file, entity, mapping, sheet="CSV", mode="strict"):
    return client.post(
        "/upload/" + endpoint,
        files={"file": file},
        data={
            "sheet_name": sheet,
            "entity_type": entity,
            "mapping_json": json.dumps(mapping),
            "import_mode": mode,
        },
    )


def count(client, table):
    return client.get("/tables/" + table).json()["total"]


def project(client):
    result = client.post(
        "/upload/record/projects",
        json={"project_name": "Reef survey", "project_code": "REEF-01"},
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


def test_schemas_match_real_columns_and_required_fields(entry):
    client, _ = entry
    schemas = client.get("/upload/schemas").json()
    assert set(schemas) == tables.TABLES - {"upload_logs"}
    for name, schema in schemas.items():
        assert set(schema["fields"]) <= set(
            database.Base.metadata.tables[name].columns.keys()
        )
        assert "id" not in schema["fields"]
    assert schemas["projects"]["required_fields"] == ["project_name", "project_code"]
    assert schemas["agents"]["required_fields"] == [
        "user_id",
        "first_name",
        "last_name",
    ]
    assert schemas["deployments"]["fields"]["time"]["type"] == "time"
    assert schemas["measurements"]["fields"]["length_mm"]["type"] == "float"
    assert "survey_code" not in schemas["observations"]["fields"]


def test_single_capture_is_visible_in_browser_with_dates_and_defaults(entry):
    client, engine = entry
    project_id = project(client)
    result = client.post(
        "/upload/record/fieldtrips",
        json={
            "project_id": project_id,
            "fieldtrip_code": "FT-01",
            "start_date": "2026-10-09",
            "duration": "3",
        },
    )
    assert result.status_code == 201, result.text
    rows = client.get("/tables/fieldtrips").json()["items"]
    assert rows[0]["start_date"] == "2026-10-09"
    assert rows[0]["duration"] == 3
    assert rows[0]["project_id"] == project_id
    with engine.connect() as connection:
        assert connection.execute(
            select(models.FieldTrip.__table__.c.start_date)
        ).scalar_one() == date(2026, 10, 9)


def test_single_capture_rejects_invalid_fields_duplicate_keys_and_missing_relations(
    entry,
):
    client, _ = entry
    assert client.post("/upload/record/projects", json={}).status_code == 422
    assert (
        client.post("/upload/record/projects", json={"name": "old schema"}).status_code
        == 422
    )
    assert client.post("/upload/record/upload_logs", json={}).status_code == 400
    assert (
        client.post(
            "/upload/record/fieldtrips",
            json={"project_id": 999, "fieldtrip_code": "FT"},
        ).status_code
        == 409
    )
    project(client)
    duplicate = client.post(
        "/upload/record/projects",
        json={"project_name": "Duplicate", "project_code": "REEF-01"},
    )
    assert duplicate.status_code == 409
    assert count(client, "projects") == 1
    assert count(client, "fieldtrips") == 0


def test_passwords_are_hashed_and_omitted_from_capture_response(entry):
    client, engine = entry
    password = "  field-secret  "
    response = client.post(
        "/upload/record/users",
        json={
            "full_name": "Field Researcher",
            "email": "field@example.org",
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    assert "password" not in response.json()
    with engine.connect() as connection:
        row = connection.execute(select(models.User.__table__)).mappings().one()
    assert bcrypt.checkpw(password.encode(), row["password"].encode())
    assert row["is_active"] is False
    assert "password" not in client.get("/tables/users").json()["items"][0]


@pytest.mark.parametrize("format", ["csv", "xlsx"])
def test_inspect_map_validate_and_import_round_trip(entry, format):
    client, _ = entry
    file = spreadsheet(
        [
            {
                "Project title": "Reef survey",
                "Code": "001",
                "Year": "2026",
                "Unused": "ignore me",
            },
            {
                "Project title": "Estuary survey",
                "Code": "002",
                "Year": "2027",
                "Unused": "ignore me",
            },
        ],
        format,
    )
    inspected = client.post("/upload/inspect", files={"file": file})
    assert inspected.status_code == 200, inspected.text
    sheet = inspected.json()["sheets"][0]
    assert sheet["row_count"] == 2
    assert sheet["preview"][0]["Code"] == "001"
    mapping = {
        "Project title": "project_name",
        "Code": "project_code",
        "Year": "start_year",
        "Unused": "__ignore__",
    }
    validated = bulk(client, "validate", file, "projects", mapping, sheet["sheet_name"])
    assert validated.status_code == 200, validated.text
    assert validated.json()["valid_count"] == 2
    assert count(client, "projects") == 0
    imported = bulk(client, "commit", file, "projects", mapping, sheet["sheet_name"])
    assert imported.status_code == 200, imported.text
    assert imported.json()["inserted_rows"] == 2
    assert imported.json()["failed_rows"] == 0
    assert count(client, "projects") == 2
    assert client.get("/tables/projects").json()["items"][0]["project_code"] == "001"
    log = client.get("/upload/history").json()[0]
    assert log["status"] == "SUCCESS"
    assert log["inserted_rows"] == 2


def test_excel_multi_sheet_selection_and_empty_sheet(entry):
    client, _ = entry
    file = spreadsheet(
        [],
        "xlsx",
        {
            "Instructions": [],
            "Roles": [{"name": "Observer", "description": "Counts fish"}],
        },
    )
    inspected = client.post("/upload/inspect", files={"file": file})
    assert inspected.status_code == 200
    sheets = inspected.json()["sheets"]
    assert [item["sheet_name"] for item in sheets] == ["Instructions", "Roles"]
    assert sheets[0]["error"]
    response = bulk(
        client,
        "commit",
        file,
        "roles",
        {"name": "name", "description": "description"},
        "Roles",
    )
    assert response.status_code == 200, response.text
    assert client.get("/tables/roles").json()["items"][0]["name"] == "Observer"


def test_row_validation_rejects_fractional_integers_and_strict_import_writes_nothing(
    entry,
):
    client, _ = entry
    file = spreadsheet(
        [
            {"project_name": "Valid", "project_code": "VALID", "start_year": "2026"},
            {
                "project_name": "Fractional",
                "project_code": "BAD",
                "start_year": "2026.5",
            },
            {"project_name": "", "project_code": "MISSING", "start_year": "2026"},
        ]
    )
    mapping = {name: name for name in ["project_name", "project_code", "start_year"]}
    validated = bulk(client, "validate", file, "projects", mapping)
    assert validated.status_code == 200
    assert validated.json()["valid_count"] == 1
    assert validated.json()["error_count"] == 2
    assert validated.json()["rows"][1]["row_number"] == 3
    assert bulk(client, "commit", file, "projects", mapping).status_code == 422
    assert count(client, "projects") == 0
    assert count(client, "upload_logs") == 0


def test_strict_constraint_failure_rolls_back_earlier_rows_and_log(entry):
    client, _ = entry
    project(client)
    file = spreadsheet(
        [
            {"project_name": "Should roll back", "project_code": "NEW"},
            {"project_name": "Duplicate", "project_code": "REEF-01"},
        ]
    )
    mapping = {"project_name": "project_name", "project_code": "project_code"}
    response = bulk(client, "commit", file, "projects", mapping)
    assert response.status_code == 409, response.text
    assert count(client, "projects") == 1
    assert count(client, "upload_logs") == 0


def test_valid_rows_mode_skips_type_and_constraint_errors_and_reports_row_numbers(
    entry,
):
    client, _ = entry
    file = spreadsheet(
        [
            {"project_name": "First", "project_code": "A", "start_year": "2026"},
            {"project_name": "Duplicate", "project_code": "A", "start_year": "2026"},
            {"project_name": "Invalid year", "project_code": "B", "start_year": "oops"},
            {"project_name": "Last", "project_code": "C", "start_year": "2027"},
        ]
    )
    response = bulk(
        client,
        "commit",
        file,
        "projects",
        {name: name for name in ["project_name", "project_code", "start_year"]},
        mode="all_valid",
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["inserted_rows"] == 2
    assert result["failed_rows"] == 2
    assert result["status"] == "PARTIAL_SUCCESS"
    assert [item["row"] for item in result["error_details"]] == [3, 4]
    assert count(client, "projects") == 2
    assert client.get("/upload/history").json()[0]["failed_rows"] == 2


def test_all_failed_rows_return_failure_and_no_records(entry):
    client, _ = entry
    # A row with some unmapped content still exercises missing required data.
    file = spreadsheet([{"name": "", "note": "Missing role"}])
    response = bulk(client, "commit", file, "roles", {"name": "name"}, mode="all_valid")
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["status"] == "FAILED"
    assert count(client, "roles") == 0


@pytest.mark.parametrize(
    "mapping",
    [
        [],
        {"Project": "does_not_exist"},
        {"missing_column": "project_name"},
        {"Project": "project_name", "Code": "project_name"},
        {"Project": "__ignore__"},
        {"Project": "project_name"},
    ],
)
def test_invalid_mappings_are_rejected(entry, mapping):
    client, _ = entry
    file = spreadsheet([{"Project": "Survey", "Code": "A"}])
    response = bulk(client, "validate", file, "projects", mapping)
    assert response.status_code == 400, response.text


def test_invalid_modes_and_files_are_rejected(entry, monkeypatch):
    client, _ = entry
    mapping = {"name": "name"}
    assert (
        bulk(
            client,
            "commit",
            spreadsheet([{"name": "Observer"}]),
            "roles",
            mapping,
            mode="anything",
        ).status_code
        == 400
    )
    for file in [
        ("records.txt", b"name\nObserver"),
        ("records.csv", b""),
        ("records.xlsx", b"not excel"),
        ("records.csv", b"name,name\nA,B"),
        ("records.csv", b"   name,name   \nA,B"),
    ]:
        assert client.post("/upload/inspect", files={"file": file}).status_code in (
            400,
            422,
        )
    monkeypatch.setattr(upload, "MAX_FILE_BYTES", 8)
    assert (
        client.post(
            "/upload/inspect", files={"file": ("records.csv", b"name\nObserver")}
        ).status_code
        == 413
    )


def test_row_limit_and_blank_rows_are_handled_without_silent_truncation(
    entry, monkeypatch
):
    client, _ = entry
    monkeypatch.setattr(upload, "MAX_ROWS", 2)
    file = ("records.csv", b"name,description\nA,one\n,\nB,two\nC,three\n")
    assert client.post("/upload/inspect", files={"file": file}).status_code == 422
    monkeypatch.setattr(upload, "MAX_ROWS", 10)
    file = ("records.csv", b"name,description\nA,one\n,\nB,two\n")
    validation = bulk(
        client,
        "validate",
        file,
        "roles",
        {"name": "name", "description": "description"},
    )
    assert validation.status_code == 200, validation.text
    assert [row["row_number"] for row in validation.json()["rows"]] == [2, 4]


@pytest.mark.parametrize("format", ["csv", "xlsx"])
def test_templates_contain_exact_writable_fields(entry, format):
    client, _ = entry
    response = client.get(f"/upload/template/projects?format={format}")
    assert response.status_code == 200
    assert f"projects_bulk_template.{format}" in response.headers["content-disposition"]
    if format == "csv":
        headers = next(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    else:
        headers = list(pd.read_excel(io.BytesIO(response.content)).columns)
    assert headers == list(client.get("/upload/schemas").json()["projects"]["fields"])


def test_date_time_boolean_and_fractional_measurements(entry):
    client, engine = entry
    project_id = project(client)
    trip_id = client.post(
        "/upload/record/fieldtrips",
        json={"project_id": project_id, "fieldtrip_code": "FT"},
    ).json()["id"]
    response = client.post(
        "/upload/record/deployments",
        json={
            "fieldtrip_id": trip_id,
            "opcode": "DEP-01",
            "date": "2026-10-09",
            "time": "12:30:45",
            "latitude": "-30.5",
            "longitude": "31.1",
            "depth_m": "20.75",
        },
    )
    assert response.status_code == 201, response.text
    deployment_id = response.json()["id"]
    measured = client.post(
        "/upload/record/measurements",
        json={
            "deployment_id": deployment_id,
            "length_mm": "102.75",
            "time_mins": "5.5",
        },
    )
    assert measured.status_code == 201
    observed = client.post(
        "/upload/record/observations",
        json={
            "deployment_id": deployment_id,
            "species": "Carcharhinus brevipinna",
            "has_fed": "No",
            "abundance": "3",
        },
    )
    assert observed.status_code == 201
    with engine.connect() as connection:
        row = connection.execute(select(models.Deployment.__table__)).mappings().one()
    assert row["time"] == time(12, 30, 45)
    assert client.get("/tables/measurements").json()["items"][0]["length_mm"] == 102.75
    assert client.get("/tables/observations").json()["items"][0]["has_fed"] is False


def test_nonfinite_numbers_bad_dates_and_secrets_are_not_echoed(entry):
    client, _ = entry
    for value in ["NaN", "Infinity", "1.5", 2**40, {"nested": 1}]:
        response = client.post(
            "/upload/record/projects",
            json={"project_name": "A", "project_code": "B", "start_year": value},
        )
        assert response.status_code == 422, response.text
    assert (
        client.post(
            "/upload/record/projects",
            json={
                "project_name": "A",
                "project_code": "B",
                "embargo_end_time": "bad date",
            },
        ).status_code
        == 422
    )
    password = "secret"
    file = spreadsheet(
        [{"full_name": "Researcher", "email": "r@example.org", "password": password}]
    )
    inspected = client.post("/upload/inspect", files={"file": file})
    assert inspected.json()["sheets"][0]["preview"][0]["password"] == "••••••••"
    validated = bulk(
        client,
        "validate",
        file,
        "users",
        {name: name for name in ["full_name", "email", "password"]},
    )
    assert validated.status_code == 200
    assert validated.json()["rows"][0]["mapped_data"]["password"] == "••••••••"
    imported = bulk(
        client,
        "commit",
        file,
        "users",
        {name: name for name in ["full_name", "email", "password"]},
    )
    assert imported.status_code == 200
