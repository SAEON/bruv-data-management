"""Field-trip model."""

from sqlalchemy import Column, Date, ForeignKey, Integer, Text, String
from sqlalchemy.orm import relationship
from db.database import Base


class FieldTrip(Base):
    __tablename__ = "fieldtrips"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True) 
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)    
    fieldtrip_code = Column(String, nullable=False, unique=True)
    fieldtrip_lead = Column(String, unique=False, nullable=True)
    equipment_manager = Column(String, nullable=True)
    data_manager = Column(String, nullable=True)
    fieldtrip_description = Column(Text, nullable=True)
    fieldtrip_objectives = Column(Text, nullable=True)
    start_date = Column(Date, nullable=True)
    duration = Column(Integer, nullable=True)
    sea_day = Column(Integer, nullable=True)
    location = Column(String, nullable=True)
    sampling_team = Column(Text, nullable=True)
    
    permit_number = Column(Integer, nullable=True)
    data_owner_contact = Column(String, nullable=True)
    data_sharing_status = Column(String, nullable=True)
    data_restriction_reason = Column(Text, nullable=True)
    embargo_end_time = Column(Date, nullable=True)
    license = Column(Text, nullable=True)
    data_access_tier = Column(String, nullable=True)
    data_confidence = Column(String, nullable=True)

    project = relationship("Project", back_populates="field_trips")
    day_sheets = relationship("DaySheet", back_populates="field_trip", cascade="all, delete-orphan")
    calibrations = relationship("Calibration", back_populates="fieldtrip", cascade="all, delete-orphan")
    deployments = relationship("Deployment", back_populates="field_trip", cascade="all, delete-orphan")
