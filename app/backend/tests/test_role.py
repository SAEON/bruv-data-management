from .test_database import client, TestingSessionLocal, engine
import pytest

try:
    from db import models
    from db.database import Base
except ModuleNotFoundError:
    from backend.db import models
    from backend.db.database import Base

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_get_roles_list_initial():
    resp = client.get("/roles")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_create_role():
    """POST /roles"""
    resp = client.post("/roles/", json={'name': 'test'})
    data = resp.json()

    assert resp.status_code == 201
    assert isinstance(data['id'], int)
    assert isinstance(data['name'], str)
    assert data.get('name') == 'test'

def test_create_role_duplicate():
    """POST /roles - duplicate name"""
    resp = client.post("/roles/", json={'name': 'test'})
    assert resp.status_code == 409
    assert resp.json()['detail'] == "Role already exists"

def test_create_role_duplicate_case_insensitive():
    """POST /roles - duplicate name with different casing ('TEST' vs 'test')"""
    resp = client.post("/roles/", json={'name': 'TEST'})
    assert resp.status_code == 409
    assert resp.json()['detail'] == "Role already exists"

def test_get_roles_list():
    resp = client.get("/roles")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(role['name'] == 'test' for role in data)

def test_get_role_by_id():
    """GET /roles/{role_id}"""
    resp_create = client.post("/roles/", json={'name': 'test_get_id'})
    role_id = resp_create.json()['id']
    
    resp = client.get(f"/roles/{role_id}")
    data = resp.json()
    
    assert resp.status_code == 200
    assert data['id'] == role_id
    assert data['name'] == 'test_get_id'

def test_get_role_by_id_not_found():
    """GET /roles/{role_id} - not found"""
    resp = client.get("/roles/999999")
    assert resp.status_code == 200
    assert resp.json() is None

def test_update_role():
    """PUT /roles/{role_id}"""
    resp_create = client.post("/roles/", json={'name': 'test_update'})
    role_id = resp_create.json()['id']
    
    resp = client.put(f"/roles/{role_id}", json={'name': 'test_updated'})
    assert resp.status_code == 202
    
    resp_get = client.get(f"/roles/{role_id}")
    assert resp_get.json()['name'] == 'test_updated'

def test_update_role_not_found():
    """PUT /roles/{role_id} - not found"""
    resp = client.put("/roles/999999", json={'name': 'new_name'})
    assert resp.status_code == 404
    assert resp.json()['detail'] == "Role with id 999999 not found"

def test_delete_role():
    """DELETE /roles/{role_id}"""
    resp_create = client.post("/roles/", json={'name': 'test_delete'})
    role_id = resp_create.json()['id']
    
    resp = client.delete(f"/roles/{role_id}")
    assert resp.status_code == 204
    
    resp_get = client.get(f"/roles/{role_id}")
    assert resp_get.status_code == 200
    assert resp_get.json() is None

def test_delete_role_not_found():
    """DELETE /roles/{role_id} - not found"""
    resp = client.delete("/roles/999999")
    assert resp.status_code == 404
    assert resp.json()['detail'] == "Role with id 999999 not found"

def test_delete_role_with_users_assigned():
    """DELETE /roles/{role_id} - with users assigned"""
    resp_create = client.post("/roles/", json={'name': 'role_with_user'})
    role_id = resp_create.json()['id']
    
    db = TestingSessionLocal()
    if hasattr(models, "UserRole"):
        user = models.User(email="test@test.com", password="pwd")
        db.add(user)
        db.commit()
        db.refresh(user)
        user_role = models.UserRole(user_id=user.id, role_id=role_id)
        db.add(user_role)
    else:
        user = models.User(email="test@test.com", password="pwd", role_id=role_id)
        db.add(user)
    db.commit()
    db.close()
    
    resp = client.delete(f"/roles/{role_id}")
    assert resp.status_code == 400
    assert resp.json()['detail'] == f"Cannot delete role {role_id}: Users are currently assigned to it."
    
    # cleanup
    db = TestingSessionLocal()
    if hasattr(models, "UserRole"):
        db.query(models.UserRole).filter(models.UserRole.role_id == role_id).delete()
    db.query(models.User).filter(models.User.email == "test@test.com").delete()
    db.commit()
    db.close()
    db.query(models.User).filter(models.User.email == "test@test.com").delete()
    db.commit()
    db.close()
