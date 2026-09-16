"""BRUV project model."""

from sqlalchemy import Column, Date, Integer, Text, String
from sqlalchemy.orm import relationship
from db.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_name = Column(String, nullable=False)
    project_code = Column(String, unique=True, index=True, nullable=False)
    project_description = Column(Text, nullable=True)
    project_lead = Column(String, nullable=True)
    financial_sponsor = Column(Text, nullable=True)
    students_involved = Column(Text, nullable=True)
    official_collaborators = Column(Text, nullable=True)
    institutes_involved = Column(Text, nullable=True)
    start_year = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    funding_source = Column(Text, nullable=True)
    status = Column(Text, nullable=True)
    data_owner = Column(String, nullable=True)
    data_owner_contact = Column(String, nullable=True)
    data_sharing_status = Column(String, nullable=True)
    data_restriction_reason = Column(Text, nullable=True)
    embargo_end_time = Column(Date, nullable=True)
    license = Column(Text, nullable=True)

    field_trips = relationship("FieldTrip", back_populates="project", cascade="all, delete-orphan")
