from pydantic import BaseModel, EmailStr
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str
    role_id: Optional[int] = None


class UserUpdate(UserBase):
    email: Optional[EmailStr] = None
    role_id: Optional[int] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    role_id: Optional[int] = None

    class Config:
        from_attributes = True
