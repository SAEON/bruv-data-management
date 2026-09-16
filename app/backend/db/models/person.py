"""Project participant model."""

from sqlalchemy import Column, ForeignKey, Integer, Text, String
from sqlalchemy.orm import relationship
from db.database import Base


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    full_name = Column(String, nullable=False)
    institution_agency_project = Column(Text, nullable=True)
    current_institution = Column(Text, nullable=True)
    email = Column(String, nullable=True)
    alternate_email = Column(String, nullable=True)

    role = relationship("Role", back_populates="people")
