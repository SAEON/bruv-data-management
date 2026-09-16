"""User-to-role assignment model."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship
from db.database import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    assigned_at = Column(DateTime, nullable=False, default=func.now())

    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")