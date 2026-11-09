from urllib import response

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from db import models, schemas, database
from starlette import status

router = APIRouter(
    prefix="/roles",
    tags=["roles"],
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_role(role: schemas.RoleCreate, db: Session = Depends(database.get_db)):
    role_name = role.name.strip()
    db_role = (
        db.query(models.Role)
        .filter(func.lower(models.Role.name) == func.lower(role_name))
        .first()
    )

    if db_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role already exists"
        )

    new_role = models.Role(name=role_name)
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role


@router.get("/", status_code=status.HTTP_200_OK)
async def read_roles(db: Session = Depends(database.get_db)):
    """Return a list of all roles"""

    roles = db.query(models.Role).all()
    return roles


@router.get("/{role_id}", status_code=status.HTTP_200_OK)
async def get_role(role_id: int, db: Session = Depends(database.get_db)):
    """Return a specific role"""

    role = db.query(models.Role).filter(models.Role.id == role_id).first()
    return role


@router.put("/{role_id}", status_code=status.HTTP_202_ACCEPTED)
async def update_role(
    role_id: int,
    role_update: schemas.RoleUpdate,
    db: Session = Depends(database.get_db),
):
    role_query = db.query(models.Role).filter(models.Role.id == role_id)
    db_role = role_query.first()

    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Role with id {role_id} not found"
        )

    new_name = role_update.name.strip()
    existing_duplicate = (
        db.query(models.Role)
        .filter(func.lower(models.Role.name) == func.lower(new_name), models.Role.id != role_id)
        .first()
    )
    if existing_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role with name '{new_name}' already exists (matches '{existing_duplicate.name}').",
        )

    role_query.update({"name": new_name}, synchronize_session=False)
    db.commit()

    return db_role


@router.delete("/{role_id}", status_code=status.HTTP_202_ACCEPTED)
async def delete_role(role_id: int, db: Session = Depends(database.get_db)):
    role_query = db.query(models.Role).filter(models.Role.id == role_id)
    db_role = role_query.first()

    if not db_role:
        raise HTTPException(status_code=404, detail=f"Role with id {role_id} not found")

    # Check if any users are assigned to this role
    if hasattr(models, "UserRole"):
        has_assigned_users = db.query(models.UserRole).filter(models.UserRole.role_id == role_id).first()
    elif hasattr(models.User, "role_id"):
        has_assigned_users = db.query(models.User).filter(models.User.role_id == role_id).first()
    else:
        has_assigned_users = False

    if has_assigned_users:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role {role_id}: Users are currently assigned to it.",
        )

    role_query.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
