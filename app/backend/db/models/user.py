from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, text
from sqlalchemy.orm import relationship
from db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(Text, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # hashed password
    is_active = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")