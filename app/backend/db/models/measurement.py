"""Video measurement model."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text, String, Float
from sqlalchemy.orm import relationship
from db.database import Base


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=False)
    filename = Column(String, nullable=True)
    frame = Column(Integer, nullable=True)
    time_mins = Column(Float, nullable=True)
    period = Column(String, nullable=True)
    period_time_mins = Column(Float, nullable=True)
    length_mm = Column(Float, nullable=True)
    precision_mm = Column(Float, nullable=True)
    rms_mm = Column(Float, nullable=True)
    range_mm = Column(Float, nullable=True)
    direction_deg = Column(Float, nullable=True)
    horz_dir_deg = Column(Float, nullable=True)
    vert_dir_deg = Column(Float, nullable=True)
    mid_x_mm = Column(Float, nullable=True)
    mid_y_mm = Column(Float, nullable=True)
    mid_z_mm = Column(Float, nullable=True)
    length_tapereader = Column(String, nullable=True)
    family = Column(String, nullable=True)
    genus = Column(String, nullable=True)
    species = Column(String, nullable=True)
    number = Column(Integer, nullable=True)
    stage = Column(String, nullable=True)
    activity = Column(String, nullable=True)
    measurement_note = Column(Text, nullable=True)
    emobs_data_type = Column(String, nullable=True)

    deployment = relationship("Deployment", back_populates="measurements")