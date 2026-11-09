import pytest
from .test_database import client, engine

try:
    from db.database import Base
except ModuleNotFoundError:
    from backend.db.database import Base


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)



def test_root_success_envelope():
    """
    Test the root endpoint ("/") to ensure it returns 200 OK
    and matches the standardized API envelope:
    {"success": True, "message": "...", "data": ..., "errors": []}
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "Marine Data Management" in data["message"]
    assert isinstance(data["data"], dict)
    assert data["data"]["status"] == "online"
    assert data["errors"] == []


def test_http_exception_envelope():
    """
    Test that 404 HTTP exceptions are formatted in the standardized envelope.
    """
    response = client.get("/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()

    assert data["success"] is False
    assert "Not Found" in data["message"]
    assert data["data"] is None
    assert isinstance(data["errors"], list)
    assert data["detail"] == data["message"]


def test_validation_error_envelope():
    """
    Test that 422 RequestValidationError is formatted with readable error messages.
    """
    # POSTing invalid payload to /roles/ (e.g. empty or wrong types)
    response = client.post("/roles/", json={})
    assert response.status_code == 422
    data = response.json()

    assert data["success"] is False
    assert "Validation" in data["message"]
    assert len(data["errors"]) > 0
    assert any("name" in err.lower() for err in data["errors"])


def test_table_search_endpoint():
    """
    Test that /tables/ returns application tables and allows querying records.
    """
    response = client.get("/tables/")
    assert response.status_code == 200
    tables = response.json().get("tables", [])
    assert isinstance(tables, list)
    assert len(tables) > 0


def test_duplicate_record_error_parsing():
    """
    Test that duplicate record integrity errors are parsed into clear, human-readable messages.
    """
    try:
        from db.schemas.response import parse_integrity_error
    except ModuleNotFoundError:
        from backend.db.schemas.response import parse_integrity_error

    # SQLite unique constraint error
    msg_sqlite, errs_sqlite = parse_integrity_error(
        Exception("UNIQUE constraint failed: roles.name")
    )
    assert "already exists" in msg_sqlite
    assert "Name" in msg_sqlite
    assert "name" in errs_sqlite[0].lower()

    # PostgreSQL unique constraint error
    msg_pg, errs_pg = parse_integrity_error(
        Exception("Key (email)=(duplicate@example.com) already exists.")
    )
    assert "already exists" in msg_pg
    assert "duplicate@example.com" in msg_pg
    assert "email" in errs_pg[0].lower()


def test_upload_duplicate_record_endpoint():
    """
    Test capturing a duplicate record returns a 409 status with clear 'already exists' message.
    """
    # Create an initial role
    client.post("/roles/", json={"name": "unique_role_name_123"})

    # Attempt to capture a record with the same role name via /upload/record/roles
    resp = client.post("/upload/record/roles", json={"name": "unique_role_name_123"})
    assert resp.status_code == 409
    data = resp.json()
    assert data["success"] is False
    assert "already exists" in data["message"].lower()


def test_upload_duplicate_record_case_insensitive():
    """
    Test capturing a duplicate record with different case (e.g. 'CASE_TEST' vs 'case_test')
    is rejected and returns 409 Conflict.
    """
    # Create role with lowercase
    client.post("/upload/record/roles", json={"name": "case_test_role"})

    # Attempt to create with UPPERCASE
    resp_upper = client.post("/upload/record/roles", json={"name": "CASE_TEST_ROLE"})
    assert resp_upper.status_code == 409
    data_upper = resp_upper.json()
    assert data_upper["success"] is False
    assert "already exists" in data_upper["message"].lower()

    # Attempt to create with MixedCase
    resp_mixed = client.post("/upload/record/roles", json={"name": "Case_Test_Role"})
    assert resp_mixed.status_code == 409
    data_mixed = resp_mixed.json()
    assert data_mixed["success"] is False
    assert "already exists" in data_mixed["message"].lower()


def test_upload_individual_edit_success():
    """
    Test editing an existing record via PUT /upload/record/{entity_type}/{record_id}.
    """
    # Create role
    create_resp = client.post("/upload/record/roles", json={"name": "edit_target_role"})
    assert create_resp.status_code == 201
    role_id = create_resp.json()["data"]["id"]

    # Update role
    put_resp = client.put(f"/upload/record/roles/{role_id}", json={"name": "edit_target_role_renamed"})
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["success"] is True
    assert "updated successfully" in data["message"].lower()
    assert data["data"]["name"] == "edit_target_role_renamed"


def test_upload_individual_edit_duplicate_case_insensitive():
    """
    Test editing a record to a name that already exists (in different case)
    is rejected with 409 Conflict.
    """
    # Create two roles
    r1 = client.post("/upload/record/roles", json={"name": "existing_omega"})
    assert r1.status_code == 201
    r2 = client.post("/upload/record/roles", json={"name": "existing_sigma"})
    assert r2.status_code == 201
    r2_id = r2.json()["data"]["id"]

    # Try to edit r2 to "EXISTING_OMEGA"
    put_resp = client.put(f"/upload/record/roles/{r2_id}", json={"name": "EXISTING_OMEGA"})
    assert put_resp.status_code == 409
    data = put_resp.json()
    assert data["success"] is False
    assert "already exists" in data["message"].lower()


def test_upload_individual_edit_not_found():
    """
    Test editing a non-existent record returns 404 Not Found.
    """
    put_resp = client.put("/upload/record/roles/999999", json={"name": "non_existent"})
    assert put_resp.status_code == 404
    data = put_resp.json()
    assert data["success"] is False
    assert "not found" in data["message"].lower()


def test_upload_bulk_edit_success():
    """
    Test updating multiple records at once via PATCH /upload/records/{entity_type}/bulk.
    """
    p1 = client.post("/upload/record/projects", json={
        "project_name": "Bulk Project 1",
        "project_code": "BP-001",
        "status": "Draft",
    })
    assert p1.status_code == 201
    id1 = p1.json()["data"]["id"]

    p2 = client.post("/upload/record/projects", json={
        "project_name": "Bulk Project 2",
        "project_code": "BP-002",
        "status": "Draft",
    })
    assert p2.status_code == 201
    id2 = p2.json()["data"]["id"]

    # Bulk update status to "Published"
    bulk_resp = client.patch("/upload/records/projects/bulk", json={
        "ids": [id1, id2],
        "updates": {"status": "Published"},
    })
    assert bulk_resp.status_code == 200
    data = bulk_resp.json()
    assert data["success"] is True
    assert data["data"]["updated_count"] == 2

    # Verify both records were updated
    get1 = client.get("/tables/projects?limit=100")
    records = get1.json().get("items", [])
    updated_records = [r for r in records if r["id"] in [id1, id2]]
    assert len(updated_records) == 2
    for r in updated_records:
        assert r["status"] == "Published"


def test_upload_bulk_edit_unique_column_rejected():
    """
    Test that bulk editing a unique column across multiple records is rejected.
    """
    p1 = client.post("/upload/record/projects", json={
        "project_name": "Bulk Unique 1",
        "project_code": "BU-001",
    })
    p2 = client.post("/upload/record/projects", json={
        "project_name": "Bulk Unique 2",
        "project_code": "BU-002",
    })
    id1 = p1.json()["data"]["id"]
    id2 = p2.json()["data"]["id"]

    # Attempt to bulk update unique column 'project_code' across multiple records
    bulk_resp = client.patch("/upload/records/projects/bulk", json={
        "ids": [id1, id2],
        "updates": {"project_code": "COLLISION-CODE"},
    })
    assert bulk_resp.status_code == 400
    data = bulk_resp.json()
    assert data["success"] is False
    assert "unique" in data["message"].lower()


def test_upload_bulk_edit_records_array_success():
    """
    Test bulk updating displayed records with individual edits in one save button
    via PATCH /upload/records/{entity_type}/bulk with {"records": [...]}.
    """
    p1 = client.post("/upload/record/projects", json={
        "project_name": "Project Alpha",
        "project_code": "P-ALPHA",
        "status": "Draft",
    })
    p2 = client.post("/upload/record/projects", json={
        "project_name": "Project Beta",
        "project_code": "P-BETA",
        "status": "Draft",
    })
    id1 = p1.json()["data"]["id"]
    id2 = p2.json()["data"]["id"]

    # Bulk update both records with different editable column values
    bulk_resp = client.patch("/upload/records/projects/bulk", json={
        "records": [
            {"id": id1, "status": "Under Review", "project_lead": "Dr. Alpha"},
            {"id": id2, "status": "Published", "project_lead": "Dr. Beta"},
        ]
    })
    assert bulk_resp.status_code == 200
    data = bulk_resp.json()
    assert data["success"] is True
    assert data["data"]["updated_count"] == 2

    # Verify both records received their individual updates
    res = client.get("/tables/projects?limit=100")
    items = {item["id"]: item for item in res.json().get("items", [])}
    assert items[id1]["status"] == "Under Review"
    assert items[id1]["project_lead"] == "Dr. Alpha"
    assert items[id2]["status"] == "Published"
    assert items[id2]["project_lead"] == "Dr. Beta"


def test_upload_bulk_edit_records_array_batch_duplicate():
    """
    Test that updating records to the same unique column value (case-insensitive)
    within the same bulk batch payload is rejected.
    """
    p1 = client.post("/upload/record/projects", json={
        "project_name": "Project Gamma",
        "project_code": "P-GAMMA",
    })
    p2 = client.post("/upload/record/projects", json={
        "project_name": "Project Delta",
        "project_code": "P-DELTA",
    })
    id1 = p1.json()["data"]["id"]
    id2 = p2.json()["data"]["id"]

    # Attempt to assign duplicate project codes with different casing
    bulk_resp = client.patch("/upload/records/projects/bulk", json={
        "records": [
            {"id": id1, "project_code": "SHARED-CODE"},
            {"id": id2, "project_code": "shared-code"},
        ]
    })
    assert bulk_resp.status_code == 409
    data = bulk_resp.json()
    assert data["success"] is False
    assert "duplicate" in data["message"].lower() or "already exists" in data["message"].lower()


def test_table_records_display_names_for_keys():
    """
    Test that /tables/{table} provides human-readable display names for foreign keys
    and primary record labels instead of raw IDs.
    """
    # Create project
    proj_resp = client.post("/upload/record/projects", json={
        "project_name": "Marine Biodiversity Study",
        "project_code": "MBS-2024",
    })
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    # Create field trip referencing project
    trip_resp = client.post("/upload/record/fieldtrips", json={
        "project_id": proj_id,
        "fieldtrip_code": "FT-MBS-01",
        "location": "False Bay",
    })
    assert trip_resp.status_code == 201
    trip_id = trip_resp.json()["data"]["id"]

    # Fetch fieldtrips table
    res = client.get("/tables/fieldtrips?limit=100")
    assert res.status_code == 200
    data = res.json()
    items = {item["id"]: item for item in data.get("items", [])}
    assert trip_id in items

    target_item = items[trip_id]
    # Check that foreign key project_id resolved to project name/code
    assert "_display_names" in target_item
    assert "project_id" in target_item["_display_names"]
    fk_label = target_item["_display_names"]["project_id"]
    assert "MBS-2024" in fk_label or "Marine Biodiversity" in fk_label

    # Check that record's primary label resolved to its name/code
    assert "_record_label" in target_item
    assert "FT-MBS-01" in target_item["_record_label"]


def test_table_first_column_label_is_id():
    """
    Test that the first column in /tables/{table} is labeled 'ID' instead of 'Record'.
    """
    res = client.get("/tables/roles?limit=5")
    assert res.status_code == 200
    cols = res.json().get("columns", [])
    assert len(cols) > 0
    id_col = cols[0]
    assert id_col["name"] == "id"
    assert id_col["label"] == "ID"


def test_upload_single_record_delete_success():
    """
    Test deleting a single record via DELETE /upload/record/{entity_type}/{record_id}.
    """
    create_resp = client.post("/upload/record/roles", json={"name": "to_be_deleted_role"})
    assert create_resp.status_code == 201
    role_id = create_resp.json()["data"]["id"]

    del_resp = client.delete(f"/upload/record/roles/{role_id}")
    assert del_resp.status_code == 200
    data = del_resp.json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"].lower()

    # Ensure record is gone
    get_resp = client.get("/tables/roles?limit=100")
    items = [r["id"] for r in get_resp.json().get("items", [])]
    assert role_id not in items


def test_upload_single_record_delete_not_found():
    """
    Test deleting a non-existent record returns 404.
    """
    del_resp = client.delete("/upload/record/roles/999999")
    assert del_resp.status_code == 404
    data = del_resp.json()
    assert data["success"] is False
    assert "not found" in data["message"].lower()


def test_upload_bulk_delete_records_success():
    """
    Test deleting multiple records via DELETE /upload/records/{entity_type}/bulk.
    """
    r1 = client.post("/upload/record/roles", json={"name": "bulk_del_1"})
    assert r1.status_code == 201
    id1 = r1.json()["data"]["id"]

    r2 = client.post("/upload/record/roles", json={"name": "bulk_del_2"})
    assert r2.status_code == 201
    id2 = r2.json()["data"]["id"]

    del_resp = client.request("DELETE", "/upload/records/roles/bulk", json={"ids": [id1, id2]})
    assert del_resp.status_code == 200
    data = del_resp.json()
    assert data["success"] is True
    assert data["deleted_count"] == 2

    # Verify both are gone
    get_resp = client.get("/tables/roles?limit=100")
    items = [r["id"] for r in get_resp.json().get("items", [])]
    assert id1 not in items
    assert id2 not in items


def test_tables_endpoint_delete_success():
    """
    Test deleting a record via DELETE /tables/{table_name}/{record_id}.
    """
    create_resp = client.post("/upload/record/roles", json={"name": "table_del_target"})
    assert create_resp.status_code == 201
    role_id = create_resp.json()["data"]["id"]

    del_resp = client.delete(f"/tables/roles/{role_id}")
    assert del_resp.status_code == 200
    data = del_resp.json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"].lower()

    # Verify it is gone
    get_resp = client.get("/tables/roles?limit=100")
    items = [r["id"] for r in get_resp.json().get("items", [])]
    assert role_id not in items


def test_bulk_upload_opcode_lookup_success():
    """
    Test bulk upload for observations where the opcode string (e.g. "BRUV_TEST_OP_01")
    is used in place of deployment_id, and is resolved to deployment.id.
    """
    import io
    import json

    # 1. Setup Project, FieldTrip, and Deployment
    proj_resp = client.post("/upload/record/projects", json={
        "project_name": "Opcode Project",
        "project_code": "OP-PROJ-01",
    })
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    trip_resp = client.post("/upload/record/fieldtrips", json={
        "project_id": proj_id,
        "fieldtrip_code": "OP-TRIP-01",
    })
    assert trip_resp.status_code == 201
    trip_id = trip_resp.json()["data"]["id"]

    dep_resp = client.post("/upload/record/deployments", json={
        "fieldtrip_id": trip_id,
        "opcode": "BRUV_TEST_OP_01",
    })
    assert dep_resp.status_code == 201
    dep_id = dep_resp.json()["data"]["id"]

    # 2. Upload CSV with opcode string
    csv_bytes = b"opcode,species,abundance\nBRUV_TEST_OP_01,Carcharodon carcharias,2\n"
    files = {"file": ("observations.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "observations",
        "mapping_json": json.dumps({"opcode": "deployment_id", "species": "species", "abundance": "abundance"}),
        "import_mode": "strict",
    }

    # Validate
    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 1
    assert val_data["error_count"] == 0
    assert val_data["rows"][0]["mapped_data"]["deployment_id"] == dep_id

    # Commit
    files_commit = {"file": ("observations.csv", io.BytesIO(csv_bytes), "text/csv")}
    com_resp = client.post("/upload/commit", files=files_commit, data=data)
    assert com_resp.status_code == 200
    com_data = com_resp.json()
    assert com_data["success"] is True
    assert com_data["inserted_rows"] == 1

    # Verify created observation record in table
    res = client.get("/tables/observations?limit=10")
    items = res.json().get("items", [])
    obs = next((item for item in items if item.get("species") == "Carcharodon carcharias"), None)
    assert obs is not None
    assert obs["deployment_id"] == dep_id


def test_bulk_upload_opcode_lookup_case_insensitive_and_fallback():
    """
    Test bulk upload resolves case-insensitively ("bruv_test_op_01")
    and falls back to integer deployment ID when provided.
    """
    import io
    import json

    # Retrieve existing deployment
    dep_list = client.get("/tables/deployments?limit=10").json().get("items", [])
    target_dep = next(item for item in dep_list if item["opcode"] == "BRUV_TEST_OP_01")
    dep_id = target_dep["id"]

    # Row 1: lowercase opcode "bruv_test_op_01"
    # Row 2: numeric ID fallback str(dep_id)
    csv_bytes = f"opcode,species\nbruv_test_op_01,Sphyrna mokarran\n{dep_id},Galeocerdo cuvier\n".encode("utf-8")
    files = {"file": ("observations.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "observations",
        "mapping_json": json.dumps({"opcode": "deployment_id", "species": "species"}),
        "import_mode": "strict",
    }

    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 2
    assert val_data["error_count"] == 0
    assert val_data["rows"][0]["mapped_data"]["deployment_id"] == dep_id
    assert val_data["rows"][1]["mapped_data"]["deployment_id"] == dep_id


def test_bulk_upload_opcode_lookup_not_found():
    """
    Test validation returns clear error when deployment opcode or ID cannot be found.
    """
    import io
    import json

    csv_bytes = b"opcode,species\nNON_EXISTENT_OPCODE_999,Test Species\n"
    files = {"file": ("observations.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "observations",
        "mapping_json": json.dumps({"opcode": "deployment_id", "species": "species"}),
        "import_mode": "strict",
    }

    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 0
    assert val_data["error_count"] == 1
    assert "not found" in val_data["rows"][0]["errors"][0].lower()
    assert "NON_EXISTENT_OPCODE_999" in val_data["rows"][0]["errors"][0]


def test_single_record_capture_with_opcode_string():
    """
    Test capturing a single record accepts opcode string in place of deployment_id.
    """
    dep_list = client.get("/tables/deployments?limit=10").json().get("items", [])
    target_dep = next(item for item in dep_list if item["opcode"] == "BRUV_TEST_OP_01")
    dep_id = target_dep["id"]

    # Using "opcode" field in record payload
    resp = client.post("/upload/record/observations", json={
        "opcode": "BRUV_TEST_OP_01",
        "species": "Carcharhinus leucas",
    })
    assert resp.status_code == 201
    obs_id = resp.json()["data"]["id"]

    # Verify the observation was created with the resolved deployment_id
    res = client.get("/tables/observations?limit=100")
    items = {item["id"]: item for item in res.json().get("items", [])}
    assert obs_id in items
    assert items[obs_id]["deployment_id"] == dep_id


def test_download_template_observations_and_measurements_uses_opcode():
    """
    Test that CSV and Excel templates for observations and measurements
    use "opcode" instead of "deployment_id" in their column headers.
    """
    import io
    import pandas as pd

    for entity in ("observations", "measurements"):
        # Test CSV template
        csv_resp = client.get(f"/upload/template/{entity}?format=csv")
        assert csv_resp.status_code == 200
        csv_content = csv_resp.content.decode("utf-8-sig")
        header_line = csv_content.splitlines()[0]
        csv_headers = [h.strip() for h in header_line.split(",")]
        assert "opcode" in csv_headers
        assert "deployment_id" not in csv_headers

        # Test Excel template
        xlsx_resp = client.get(f"/upload/template/{entity}?format=xlsx")
        assert xlsx_resp.status_code == 200
        df = pd.read_excel(io.BytesIO(xlsx_resp.content))
        xlsx_headers = list(df.columns)
        assert "opcode" in xlsx_headers
        assert "deployment_id" not in xlsx_headers


def test_bulk_upload_using_downloaded_template_with_opcode():
    """
    Test end-to-end bulk upload workflow:
    1. Download observation and measurement CSV templates.
    2. Fill records referencing deployment opcode.
    3. Validate and commit to verify successful import.
    """
    import io
    import json

    dep_list = client.get("/tables/deployments?limit=10").json().get("items", [])
    target_dep = next(item for item in dep_list if item["opcode"] == "BRUV_TEST_OP_01")
    dep_id = target_dep["id"]

    # Observations: fill downloaded template
    obs_resp = client.get("/upload/template/observations?format=csv")
    assert obs_resp.status_code == 200
    headers = obs_resp.content.decode("utf-8-sig").splitlines()[0].split(",")
    row_vals = ["" for _ in headers]
    row_vals[headers.index("opcode")] = "BRUV_TEST_OP_01"
    row_vals[headers.index("species")] = "Sphyrna mokarran"
    row_vals[headers.index("abundance")] = "3"
    csv_body = ",".join(headers) + "\n" + ",".join(row_vals) + "\n"

    files = {"file": ("observations.csv", io.BytesIO(csv_body.encode("utf-8-sig")), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "observations",
        "mapping_json": json.dumps({"opcode": "opcode", "species": "species", "abundance": "abundance"}),
        "import_mode": "strict",
    }
    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    assert val_resp.json()["valid_count"] == 1
    assert val_resp.json()["error_count"] == 0

    files = {"file": ("observations.csv", io.BytesIO(csv_body.encode("utf-8-sig")), "text/csv")}
    com_resp = client.post("/upload/commit", files=files, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 1

    # Verify committed observation has the correct foreign key
    obs_list = client.get("/tables/observations?limit=100").json().get("items", [])
    created_obs = next(o for o in obs_list if o.get("species") == "Sphyrna mokarran")
    assert created_obs["deployment_id"] == dep_id

    # Measurements: fill downloaded template
    meas_resp = client.get("/upload/template/measurements?format=csv")
    assert meas_resp.status_code == 200
    m_headers = meas_resp.content.decode("utf-8-sig").splitlines()[0].split(",")
    m_row_vals = ["" for _ in m_headers]
    m_row_vals[m_headers.index("opcode")] = "BRUV_TEST_OP_01"
    m_row_vals[m_headers.index("species")] = "Rhincodon typus"
    m_row_vals[m_headers.index("length_mm")] = "4500"
    m_csv_body = ",".join(m_headers) + "\n" + ",".join(m_row_vals) + "\n"

    m_files = {"file": ("measurements.csv", io.BytesIO(m_csv_body.encode("utf-8-sig")), "text/csv")}
    m_data = {
        "sheet_name": "CSV",
        "entity_type": "measurements",
        "mapping_json": json.dumps({"opcode": "opcode", "species": "species", "length_mm": "length_mm"}),
        "import_mode": "strict",
    }
    m_val_resp = client.post("/upload/validate", files=m_files, data=m_data)
    assert m_val_resp.status_code == 200
    assert m_val_resp.json()["valid_count"] == 1
    assert m_val_resp.json()["error_count"] == 0

    m_files = {"file": ("measurements.csv", io.BytesIO(m_csv_body.encode("utf-8-sig")), "text/csv")}
    m_com_resp = client.post("/upload/commit", files=m_files, data=m_data)
    assert m_com_resp.status_code == 200
    assert m_com_resp.json()["inserted_rows"] == 1

    meas_list = client.get("/tables/measurements?limit=100").json().get("items", [])
    created_meas = next(m for m in meas_list if m.get("species") == "Rhincodon typus")
    assert created_meas["deployment_id"] == dep_id


def test_download_template_analysis_period_uses_opcode():
    """
    Test that CSV and Excel templates for analysis_periods (and singular analysis_period)
    use "opcode" instead of "deployment_id" in their column headers.
    """
    import io
    import pandas as pd

    for entity in ("analysis_periods", "analysis_period"):
        # Test CSV template
        csv_resp = client.get(f"/upload/template/{entity}?format=csv")
        assert csv_resp.status_code == 200
        csv_content = csv_resp.content.decode("utf-8-sig")
        header_line = csv_content.splitlines()[0]
        csv_headers = [h.strip() for h in header_line.split(",")]
        assert "opcode" in csv_headers
        assert "deployment_id" not in csv_headers

        # Test Excel template
        xlsx_resp = client.get(f"/upload/template/{entity}?format=xlsx")
        assert xlsx_resp.status_code == 200
        df = pd.read_excel(io.BytesIO(xlsx_resp.content))
        xlsx_headers = list(df.columns)
        assert "opcode" in xlsx_headers
        assert "deployment_id" not in xlsx_headers


def test_bulk_upload_analysis_periods_using_downloaded_template_with_opcode():
    """
    Test end-to-end bulk upload workflow for analysis_periods:
    1. Download analysis_period template.
    2. Populate record with deployment opcode.
    3. Validate and commit to verify successful foreign key resolution and record insertion.
    """
    import io
    import json

    dep_list = client.get("/tables/deployments?limit=10").json().get("items", [])
    target_dep = next(item for item in dep_list if item["opcode"] == "BRUV_TEST_OP_01")
    dep_id = target_dep["id"]

    # Download analysis_period CSV template
    ap_resp = client.get("/upload/template/analysis_period?format=csv")
    assert ap_resp.status_code == 200
    headers = ap_resp.content.decode("utf-8-sig").splitlines()[0].split(",")
    row_vals = ["" for _ in headers]
    row_vals[headers.index("opcode")] = "BRUV_TEST_OP_01"
    row_vals[headers.index("period")] = "Test Analysis Period A"
    row_vals[headers.index("start_time_mins")] = "5.5"
    row_vals[headers.index("end_time_mins")] = "65.5"
    csv_body = ",".join(headers) + "\n" + ",".join(row_vals) + "\n"

    files = {"file": ("analysis_periods.csv", io.BytesIO(csv_body.encode("utf-8-sig")), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "analysis_period",
        "mapping_json": json.dumps({
            "opcode": "opcode",
            "period": "period",
            "start_time_mins": "start_time_mins",
            "end_time_mins": "end_time_mins",
        }),
        "import_mode": "strict",
    }
    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    assert val_resp.json()["valid_count"] == 1
    assert val_resp.json()["error_count"] == 0

    files = {"file": ("analysis_periods.csv", io.BytesIO(csv_body.encode("utf-8-sig")), "text/csv")}
    com_resp = client.post("/upload/commit", files=files, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 1

    # Verify committed analysis period has the correct resolved deployment_id
    ap_list = client.get("/tables/analysis_periods?limit=100").json().get("items", [])
    created_ap = next(a for a in ap_list if a.get("period") == "Test Analysis Period A")
    assert created_ap["deployment_id"] == dep_id


def test_foreign_key_number_stored_directly():
    """
    Test that when a foreign key in bulk upload is a number,
    it is stored directly as an integer ID without requiring text lookup.
    """
    import io
    import json

    # Create a project
    proj_resp = client.post("/upload/record/projects", json={
        "project_name": "Direct Number FK Project",
        "project_code": "NUM-FK-01",
    })
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    # Upload fieldtrip providing project_id as numeric integer and numeric string
    csv_bytes = f"project_id,fieldtrip_code\n{proj_id},NUM-TRIP-01\n{str(proj_id)},NUM-TRIP-02\n".encode("utf-8")
    files = {"file": ("fieldtrips.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "fieldtrips",
        "mapping_json": json.dumps({"project_id": "project_id", "fieldtrip_code": "fieldtrip_code"}),
        "import_mode": "strict",
    }

    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 2
    assert val_data["error_count"] == 0
    assert val_data["rows"][0]["mapped_data"]["project_id"] == proj_id
    assert val_data["rows"][1]["mapped_data"]["project_id"] == proj_id

    # Commit and verify
    files_commit = {"file": ("fieldtrips.csv", io.BytesIO(csv_bytes), "text/csv")}
    com_resp = client.post("/upload/commit", files=files_commit, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 2


def test_foreign_key_text_lookup_on_primary_table():
    """
    Test that when a foreign key is text, it looks up on the primary table
    and uses that record's primary key ID.
    """
    import io
    import json

    # 1. Setup primary table record (Project)
    proj_resp = client.post("/upload/record/projects", json={
        "project_name": "Text Lookup Project",
        "project_code": "TXT-LOOKUP-PROJ",
    })
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    # 2. Upload fieldtrip where project_id contains text:
    # Row 1: exact match on project_code ("TXT-LOOKUP-PROJ")
    # Row 2: case-insensitive match on project_code ("txt-lookup-proj")
    # Row 3: match on project_name ("Text Lookup Project")
    csv_bytes = (
        b"project_id,fieldtrip_code\n"
        b"TXT-LOOKUP-PROJ,TXT-TRIP-01\n"
        b"txt-lookup-proj,TXT-TRIP-02\n"
        b"Text Lookup Project,TXT-TRIP-03\n"
    )
    files = {"file": ("fieldtrips.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "fieldtrips",
        "mapping_json": json.dumps({"project_id": "project_id", "fieldtrip_code": "fieldtrip_code"}),
        "import_mode": "strict",
    }

    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 3
    assert val_data["error_count"] == 0
    assert val_data["rows"][0]["mapped_data"]["project_id"] == proj_id
    assert val_data["rows"][1]["mapped_data"]["project_id"] == proj_id
    assert val_data["rows"][2]["mapped_data"]["project_id"] == proj_id

    # Commit and verify
    files_commit = {"file": ("fieldtrips.csv", io.BytesIO(csv_bytes), "text/csv")}
    com_resp = client.post("/upload/commit", files=files_commit, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 3


def test_foreign_key_text_lookup_not_found():
    """
    Test that when a foreign key text lookup finds no matching record on the primary table,
    a clear validation error is returned.
    """
    import io
    import json

    csv_bytes = b"project_id,fieldtrip_code\nNON_EXISTENT_PROJECT_999,FAIL-TRIP-01\n"
    files = {"file": ("fieldtrips.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "fieldtrips",
        "mapping_json": json.dumps({"project_id": "project_id", "fieldtrip_code": "fieldtrip_code"}),
        "import_mode": "strict",
    }

    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 0
    assert val_data["error_count"] == 1
    assert "not found" in val_data["rows"][0]["errors"][0].lower()
    assert "NON_EXISTENT_PROJECT_999" in val_data["rows"][0]["errors"][0]


def test_bulk_upload_mixed_foreign_key_number_and_text():
    """
    Test bulk upload where one row supplies an ID as a number (stored directly)
    and another row supplies text (looked up on the primary table).
    """
    import io
    import json

    proj_resp = client.post("/upload/record/projects", json={
        "project_name": "Mixed Mode Project",
        "project_code": "MIXED-PROJ-01",
    })
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    # Row 1 has number proj_id, Row 2 has text "MIXED-PROJ-01"
    csv_bytes = f"project_id,fieldtrip_code\n{proj_id},MIX-TRIP-01\nMIXED-PROJ-01,MIX-TRIP-02\n".encode("utf-8")
    files = {"file": ("fieldtrips.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "fieldtrips",
        "mapping_json": json.dumps({"project_id": "project_id", "fieldtrip_code": "fieldtrip_code"}),
        "import_mode": "strict",
    }

    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 2
    assert val_data["error_count"] == 0
    assert val_data["rows"][0]["mapped_data"]["project_id"] == proj_id
    assert val_data["rows"][1]["mapped_data"]["project_id"] == proj_id

    files_commit = {"file": ("fieldtrips.csv", io.BytesIO(csv_bytes), "text/csv")}
    com_resp = client.post("/upload/commit", files=files_commit, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 2


def test_foreign_key_role_lookup_and_numeric_store():
    """
    Test foreign key resolution for roles when uploading people:
    - Numeric role_id is stored directly.
    - Text role_id looks up the role by name on the roles primary table.
    """
    import io
    import json

    # Create a role
    role_resp = client.post("/roles/", json={"name": "Marine Ecologist", "description": "Field ecologist"})
    assert role_resp.status_code == 201
    role_id = role_resp.json()["id"]

    # Upload people: row 1 with number role_id, row 2 with text role name
    csv_bytes = f"full_name,role_id\nAlice Smith,{role_id}\nBob Jones,Marine Ecologist\n".encode("utf-8")
    files = {"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "people",
        "mapping_json": json.dumps({"full_name": "full_name", "role_id": "role_id"}),
        "import_mode": "strict",
    }

    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 2
    assert val_data["error_count"] == 0
    assert val_data["rows"][0]["mapped_data"]["role_id"] == role_id
    assert val_data["rows"][1]["mapped_data"]["role_id"] == role_id

    files_commit = {"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")}
    com_resp = client.post("/upload/commit", files=files_commit, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 2


def test_day_sheet_depth_string_capture_and_bulk_upload():
    """
    Test that day_sheet.depth accepts string values (e.g. '15-20m', 'shallow')
    both in single record capture and in bulk upload.
    """
    import io
    import json

    # 1. Setup Project and Fieldtrip
    proj_resp = client.post("/upload/record/projects", json={
        "project_name": "DaySheet Depth Test Project",
        "project_code": "DS-PROJ-01",
    })
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    trip_resp = client.post("/upload/record/fieldtrips", json={
        "project_id": proj_id,
        "fieldtrip_code": "DS-TRIP-01",
    })
    assert trip_resp.status_code == 201
    trip_id = trip_resp.json()["data"]["id"]

    # 2. Single record capture with string depth
    ds_resp = client.post("/upload/record/day_sheets", json={
        "fieldtrip_id": trip_id,
        "date": "2026-10-15",
        "depth": "15-25m",
        "wind": "Light breeze",
    })
    assert ds_resp.status_code == 201

    # Verify retrieved record has string depth
    rec_resp = client.get("/tables/day_sheets?search=15-25m")
    assert rec_resp.status_code == 200
    items = rec_resp.json()["items"]
    assert any(item["depth"] == "15-25m" for item in items)

    # 3. Bulk upload with string depth
    csv_bytes = f"fieldtrip_id,depth,wind\n{trip_id},shallow reef,Moderate\nDS-TRIP-01,30-45m,Calm\n".encode("utf-8")
    files = {"file": ("day_sheets.csv", io.BytesIO(csv_bytes), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "day_sheets",
        "mapping_json": json.dumps({"fieldtrip_id": "fieldtrip_id", "depth": "depth", "wind": "wind"}),
        "import_mode": "strict",
    }
    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 2
    assert val_data["error_count"] == 0
    assert val_data["rows"][0]["mapped_data"]["depth"] == "shallow reef"
    assert val_data["rows"][1]["mapped_data"]["depth"] == "30-45m"

    files_commit = {"file": ("day_sheets.csv", io.BytesIO(csv_bytes), "text/csv")}
    com_resp = client.post("/upload/commit", files=files_commit, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 2


def test_download_table_records_endpoint():
    """
    Test GET /tables/{table_name}/download endpoint downloads records as CSV and Excel.
    """
    import io
    import pandas as pd

    # Download projects as CSV
    resp = client.get("/tables/projects/download?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert 'filename="projects_records.csv"' in resp.headers["content-disposition"]
    df = pd.read_csv(io.BytesIO(resp.content), encoding="utf-8-sig")
    assert "project_code" in df.columns

    # Download projects as Excel
    resp_xlsx = client.get("/tables/projects/download?format=xlsx")
    assert resp_xlsx.status_code == 200
    assert "openxmlformats-officedocument" in resp_xlsx.headers["content-type"]
    assert 'filename="projects_records.xlsx"' in resp_xlsx.headers["content-disposition"]
    df_xlsx = pd.read_excel(io.BytesIO(resp_xlsx.content))
    assert "project_code" in df_xlsx.columns


def test_download_selected_table_records_endpoint():
    """
    Test GET and POST /tables/{table_name}/download with selected record IDs.
    """
    import io
    import pandas as pd

    projects_resp = client.get("/tables/projects")
    assert projects_resp.status_code == 200
    items = projects_resp.json()["items"]
    assert len(items) >= 1
    target_id = items[0]["id"]
    target_code = items[0]["project_code"]

    # 1. Download selected record via GET comma-separated ids
    resp = client.get(f"/tables/projects/download?format=csv&ids={target_id}")
    assert resp.status_code == 200
    assert "filename=\"projects_selected_records.csv\"" in resp.headers["content-disposition"]
    df = pd.read_csv(io.BytesIO(resp.content), encoding="utf-8-sig")
    assert len(df) == 1
    assert df.iloc[0]["project_code"] == target_code

    # 2. Download selected record via POST
    post_resp = client.post("/tables/projects/download", json={"ids": [target_id], "format": "xlsx"})
    assert post_resp.status_code == 200
    assert "filename=\"projects_selected_records.xlsx\"" in post_resp.headers["content-disposition"]
    df_xlsx = pd.read_excel(io.BytesIO(post_resp.content))
    assert len(df_xlsx) == 1
    assert df_xlsx.iloc[0]["project_code"] == target_code


def test_calibration_boolean_coercion_yes_no_true_false_1_2():
    """
    Verify coerce_value accurately converts Yes/No, True/False, 1/2, and rejects invalid inputs.
    """
    from routers.upload import coerce_value

    # True equivalents
    for val in (True, "True", "true", "TRUE", "Yes", "yes", "YES", "y", "Y", "t", "T", 1, "1", 1.0, "1.0"):
        res, err = coerce_value(val, "bool")
        assert res is True, f"Failed for {val!r}"
        assert err is None

    # False equivalents (including None, empty string, 2, 0, No, False)
    for val in (False, "False", "false", "FALSE", "No", "no", "NO", "n", "N", "f", "F", 0, "0", 0.0, "0.0", 2, "2", 2.0, "2.0", "", None):
        res, err = coerce_value(val, "bool")
        assert res is False, f"Failed for {val!r}"
        assert err is None

    # Invalid values
    for val in ("maybe", 3, "3", "unknown", -1, "invalid"):
        res, err = coerce_value(val, "bool")
        assert res is None
        assert err == "Use Yes or No."


def test_calibration_single_record_capture_and_bulk_upload_boolean():
    """
    Test calibration record capture and bulk upload using Yes/No, True/False, and 1/2.
    """
    import io
    import json

    # 1. Ensure project and fieldtrip exist
    proj_resp = client.post("/upload/record/projects", json={
        "project_code": "PROJ-CALIB-01",
        "project_name": "Calibration Survey Project",
    })
    assert proj_resp.status_code in (200, 201)
    proj_id = proj_resp.json()["id"]

    ft_resp = client.post("/upload/record/fieldtrips", json={
        "fieldtrip_code": "TRIP-CALIB-01",
        "fieldtrip_description": "Calibration Trip",
        "project_id": proj_id,
    })
    assert ft_resp.status_code in (200, 201)
    trip_id = ft_resp.json()["id"]

    # 2. Capture single calibration records with "Yes", "No", 1, 2
    rec1 = client.post("/upload/record/calibrations", json={
        "fieldtrip_id": trip_id,
        "cal_type": "pool",
        "camera_type": "GoPro Hero",
        "camera_pair": "Pair 1",
        "cal_success": "Yes",
    })
    assert rec1.status_code in (200, 201)
    rec1_id = rec1.json()["id"]

    rec2 = client.post("/upload/record/calibrations", json={
        "fieldtrip_id": trip_id,
        "cal_type": "lab",
        "camera_type": "GoPro Hero",
        "camera_pair": "Pair 2",
        "cal_success": "2",
    })
    assert rec2.status_code in (200, 201)
    rec2_id = rec2.json()["id"]

    rec3 = client.post("/upload/record/calibrations", json={
        "fieldtrip_id": trip_id,
        "cal_type": "stereo",
        "camera_type": "Sony",
        "camera_pair": "Pair 3",
        "cal_success": 1,
    })
    assert rec3.status_code in (200, 201)
    rec3_id = rec3.json()["id"]

    # Verify directly from database via /tables/calibrations
    cal_records = client.get("/tables/calibrations?limit=100").json().get("items", [])
    cal_map = {r["id"]: r for r in cal_records}
    assert cal_map[rec1_id]["cal_success"] is True
    assert cal_map[rec2_id]["cal_success"] is False
    assert cal_map[rec3_id]["cal_success"] is True

    # 3. Bulk upload calibration records with mixed Yes/No, True/False, 1/2, 1.0, 2.0
    csv_content = f"""fieldtrip_id,camera_type,camera_pair,cal_success
TRIP-CALIB-01,GoPro,Pair A,True
{trip_id},GoPro,Pair B,False
TRIP-CALIB-01,GoPro,Pair C,1
{trip_id},GoPro,Pair D,2
TRIP-CALIB-01,GoPro,Pair E,Yes
{trip_id},GoPro,Pair F,No
"""
    files = {"file": ("calibrations.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "calibrations",
        "mapping_json": json.dumps({
            "fieldtrip_id": "fieldtrip_id",
            "camera_type": "camera_type",
            "camera_pair": "camera_pair",
            "cal_success": "cal_success",
        }),
        "import_mode": "strict",
    }
    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 6
    assert val_data["error_count"] == 0

    assert val_data["rows"][0]["mapped_data"]["cal_success"] is True
    assert val_data["rows"][1]["mapped_data"]["cal_success"] is False
    assert val_data["rows"][2]["mapped_data"]["cal_success"] is True
    assert val_data["rows"][3]["mapped_data"]["cal_success"] is False
    assert val_data["rows"][4]["mapped_data"]["cal_success"] is True
    assert val_data["rows"][5]["mapped_data"]["cal_success"] is False

    # Commit bulk upload
    files_com = {"file": ("calibrations.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    com_resp = client.post("/upload/commit", files=files_com, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 6

    # 4. Verify search in tables browser endpoint
    search_yes = client.get("/tables/calibrations?search=Yes")
    assert search_yes.status_code == 200
    assert search_yes.json()["total"] >= 5
    assert all(item["cal_success"] is True for item in search_yes.json()["items"])

    search_no = client.get("/tables/calibrations?search=No")
    assert search_no.status_code == 200
    assert search_no.json()["total"] >= 4
    assert all(item["cal_success"] is False for item in search_no.json()["items"])


def test_deployment_current_kn_string_support():
    """
    Test that current_kn on deployments accepts string values (e.g. '1.5', '1-2 knots', 'moderate')
    in single record creation and bulk upload.
    """
    import io
    import json

    # 1. Setup Project & FieldTrip
    proj_resp = client.post("/upload/record/projects", json={
        "project_code": "PROJ-CURR-01",
        "project_name": "Current Test Project",
    })
    assert proj_resp.status_code in (200, 201)
    proj_id = proj_resp.json()["id"]

    ft_resp = client.post("/upload/record/fieldtrips", json={
        "fieldtrip_code": "TRIP-CURR-01",
        "fieldtrip_description": "Current Test Trip",
        "project_id": proj_id,
    })
    assert ft_resp.status_code in (200, 201)
    trip_id = ft_resp.json()["id"]

    # 2. Single capture deployment with string current_kn
    dep_resp = client.post("/upload/record/deployments", json={
        "fieldtrip_id": trip_id,
        "opcode": "OP-CURR-01",
        "current_kn": "1.5 knots",
    })
    assert dep_resp.status_code in (200, 201)
    dep_id = dep_resp.json()["id"]

    # Fetch and verify
    get_resp = client.get(f"/tables/deployments")
    assert get_resp.status_code == 200
    dep_records = {d["id"]: d for d in get_resp.json().get("items", [])}
    assert dep_records[dep_id]["current_kn"] == "1.5 knots"

    # 3. Bulk upload validation with string current_kn
    csv_content = f"""fieldtrip_id,opcode,current_kn
{trip_id},OP-CURR-02,0.8
TRIP-CURR-01,OP-CURR-03,2-3 kn
{trip_id},OP-CURR-04,strong
"""
    files = {"file": ("deployments.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    data = {
        "sheet_name": "CSV",
        "entity_type": "deployments",
        "mapping_json": json.dumps({
            "fieldtrip_id": "fieldtrip_id",
            "opcode": "opcode",
            "current_kn": "current_kn",
        }),
        "import_mode": "strict",
    }
    val_resp = client.post("/upload/validate", files=files, data=data)
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid_count"] == 3
    assert val_data["error_count"] == 0
    assert val_data["rows"][0]["mapped_data"]["current_kn"] == "0.8"
    assert val_data["rows"][1]["mapped_data"]["current_kn"] == "2-3 kn"
    assert val_data["rows"][2]["mapped_data"]["current_kn"] == "strong"

    # Commit bulk upload
    files_com = {"file": ("deployments.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    com_resp = client.post("/upload/commit", files=files_com, data=data)
    assert com_resp.status_code == 200
    assert com_resp.json()["inserted_rows"] == 3


def test_form_boolean_yes_no_and_default_false():
    """
    Test that boolean fields in single-record capture and database defaults:
    - Default to False when omitted or empty
    - Support 'Yes' -> True and 'No' -> False
    """
    # 1. Setup Project, Fieldtrip, Deployment
    proj_resp = client.post("/upload/record/projects", json={
        "project_code": "PROJ-BOOL-01",
        "project_name": "Boolean Form Project",
    })
    assert proj_resp.status_code in (200, 201)
    proj_id = proj_resp.json()["id"]

    ft_resp = client.post("/upload/record/fieldtrips", json={
        "fieldtrip_code": "TRIP-BOOL-01",
        "fieldtrip_description": "Boolean Form Trip",
        "project_id": proj_id,
    })
    assert ft_resp.status_code in (200, 201)
    trip_id = ft_resp.json()["id"]

    dep_resp = client.post("/upload/record/deployments", json={
        "fieldtrip_id": trip_id,
        "opcode": "OP-BOOL-01",
    })
    assert dep_resp.status_code in (200, 201)
    dep_id = dep_resp.json()["id"]

    # 2. Calibration omitting cal_success -> should default to False
    cal1_resp = client.post("/upload/record/calibrations", json={
        "fieldtrip_id": trip_id,
        "camera_type": "GoPro",
        "camera_pair": "Default Pair",
    })
    assert cal1_resp.status_code in (200, 201)
    cal1_id = cal1_resp.json()["id"]

    # 3. Calibration with cal_success: 'Yes' -> should be True
    cal2_resp = client.post("/upload/record/calibrations", json={
        "fieldtrip_id": trip_id,
        "camera_type": "GoPro",
        "camera_pair": "Yes Pair",
        "cal_success": "Yes",
    })
    assert cal2_resp.status_code in (200, 201)
    cal2_id = cal2_resp.json()["id"]

    # 4. Calibration with cal_success: 'No' -> should be False
    cal3_resp = client.post("/upload/record/calibrations", json={
        "fieldtrip_id": trip_id,
        "camera_type": "GoPro",
        "camera_pair": "No Pair",
        "cal_success": "No",
    })
    assert cal3_resp.status_code in (200, 201)
    cal3_id = cal3_resp.json()["id"]

    # Verify calibrations via /tables/calibrations
    cal_items = {c["id"]: c for c in client.get("/tables/calibrations?limit=100").json().get("items", [])}
    assert cal_items[cal1_id]["cal_success"] is False
    assert cal_items[cal2_id]["cal_success"] is True
    assert cal_items[cal3_id]["cal_success"] is False

    # 5. Observation omitting has_fed -> should default to False
    obs1_resp = client.post("/upload/record/observations", json={
        "deployment_id": dep_id,
        "species": "Carcharhinus galapagensis",
        "abundance": 1,
    })
    assert obs1_resp.status_code in (200, 201)
    obs1_id = obs1_resp.json()["id"]

    # 6. Observation with has_fed: 'Yes' -> should be True
    obs2_resp = client.post("/upload/record/observations", json={
        "deployment_id": dep_id,
        "species": "Carcharhinus galapagensis",
        "abundance": 2,
        "has_fed": "Yes",
    })
    assert obs2_resp.status_code in (200, 201)
    obs2_id = obs2_resp.json()["id"]

    # Verify observations via /tables/observations
    obs_items = {o["id"]: o for o in client.get("/tables/observations?limit=100").json().get("items", [])}
    assert obs_items[obs1_id]["has_fed"] is False
    assert obs_items[obs2_id]["has_fed"] is True


def test_get_database_schema():
    response = client.get("/tables/schema")
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    assert "edges" in data
    assert "summary" in data
    assert data["summary"]["total_tables"] >= 14
    assert data["summary"]["total_columns"] > 100
    table_names = {t["name"] for t in data["tables"]}
    assert "observations" in table_names
    assert "deployments" in table_names
    assert "fieldtrips" in table_names
    assert "projects" in table_names


def test_get_single_table_schema():
    response = client.get("/tables/deployments/schema")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "deployments"
    assert "columns" in data
    assert len(data["columns"]) > 0
    assert "primary_keys" in data
    assert "id" in data["primary_keys"]
    assert "outgoing_relationships" in data
    assert any(rel["target_table"] == "fieldtrips" for rel in data["outgoing_relationships"])

