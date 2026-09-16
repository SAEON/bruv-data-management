from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from db.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)

    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    people = relationship("Person", back_populates="role")