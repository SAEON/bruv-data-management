"""Camera calibration model."""

from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Text, String
from sqlalchemy.orm import relationship
from db.database import Base


class Calibration(Base):
    __tablename__ = "calibrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fieldtrip_id = Column(Integer, ForeignKey("fieldtrips.id"), nullable=False)
    date = Column(Date, nullable=True)
    cal_type = Column(String, nullable=True)
    person_pool_cal = Column(String, nullable=True)    
    person_lab_cal = Column(String, nullable=True)    
    cube_name = Column(String, nullable=True)
    distance_bar_name = Column(String, nullable=True)
    camera_type = Column(String, nullable=True)
    camera_pair = Column(String, nullable=True)
    camera_no = Column(Integer, nullable=True)
    card_no = Column(String, nullable=True)
    cal_success = Column(Boolean, default=False)
    cal_precision = Column(String, nullable=True)
    calib_file_name = Column(String, nullable=True)

    fieldtrip = relationship("FieldTrip", back_populates="calibrations")
