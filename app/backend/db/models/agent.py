from db.database import Base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func


class Agent(Base):
    __tablename__ = "agent"

    id = Column(Integer, primary_key=True, index=True)
    firstname = Column(String)
    lastname = Column(String)
    initials = Column(String)
    title = Column(String)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)   # hashed password
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())

    def __repr__(self):
        return f"<Agent(id={self.id}, email={self.email})>"
