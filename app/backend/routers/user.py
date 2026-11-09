from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from db import models, schemas, database, auth
from starlette import status

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    email_clean = user.email.strip()
    db_user = (
        db.query(models.User)
        .filter(func.lower(models.User.email) == func.lower(email_clean))
        .first()
    )

    if db_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    hashed_pwd = auth.get_password_hash(user.password) if hasattr(auth, "get_password_hash") else user.password
    new_user = models.User(email=email_clean, password=hashed_pwd)
    if hasattr(user, "role_id") and hasattr(models.User, "role_id"):
        new_user.role_id = user.role_id

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
