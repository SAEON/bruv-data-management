"""BRUV equipment deployment model."""

from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, Text, Time, String
from sqlalchemy.orm import relationship
from db.database import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fieldtrip_id = Column(Integer, ForeignKey("fieldtrips.id"), nullable=False)
    opcode = Column(Text, nullable=False, unique=True)
    date = Column(Date, nullable=True)
    alt_opcode = Column(String, nullable=True)
    location = Column(String, nullable=True)
    wpt_name = Column(String, nullable=True)
    equip_desc = Column(Text, nullable=True)
    l_cam = Column(Integer, nullable=True)
    r_cam = Column(Integer, nullable=True)
    l_card = Column(Text, nullable=True)
    r_card = Column(Text, nullable=True)
    bait_type = Column(Text, nullable=True)
    bait_vol_kg = Column(Integer, nullable=True)
    lights = Column(Text, nullable=True)
    treatments = Column(Text, nullable=True)
    temp = Column(Float, nullable=True)
    time = Column(Time, nullable=True)
    depth_m = Column(Float, nullable=True)
    sensor_depth_m = Column(Integer, nullable=True)
    light_concentration = Column(String, nullable=True)
    current_kn = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    drop_waypoint = Column(Integer, nullable=True)
    field_comments = Column(Text, nullable=True)
    footage_success = Column(Integer, nullable=True) #? Bool
    cal_to_use = Column(String, nullable=True)
    analysis_notes = Column(Text, nullable=True)
    sample_status = Column(Text, nullable=True)
    sample_status_comments = Column(Text, nullable=True)
    emobs = Column(String, nullable=True)    

    field_trip = relationship("FieldTrip", back_populates="deployments")
    observations = relationship("Observation", back_populates="deployment", cascade="all, delete-orphan")
    measurements = relationship("Measurement", back_populates="deployment", cascade="all, delete-orphan")
    analysis_periods = relationship("AnalysisPeriod", back_populates="deployment", cascade="all, delete-orphan")
