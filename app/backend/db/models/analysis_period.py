"""Video analysis-period model."""

from sqlalchemy import Column, ForeignKey, Integer, Text, String, Float
from sqlalchemy.orm import relationship
from db.database import Base


class AnalysisPeriod(Base):
    __tablename__ = "analysis_periods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=False)
    period = Column(String, nullable=True)
    start_filename = Column(String, nullable=True)
    start_frame = Column(Integer, nullable=True)
    start_time_mins = Column(Float, nullable=True)
    end_filename = Column(Text, nullable=True)
    end_frame = Column(Integer, nullable=True)
    end_time_mins = Column(Float, nullable=True)
    period_length_frames = Column(Integer, nullable=True)
    period_length_mins = Column(Float, nullable=True)
    tapereader = Column(String, nullable=True)
    depth = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)
    sample_status = Column(String, nullable=True)
    bottom_type = Column(String, nullable=True)
    water_column = Column(Integer, nullable=True)
    obstruction = Column(Integer, nullable=True)
    visibility = Column(Float, nullable=True)
    length_tapereader = Column(Integer, nullable=True)
    quality_control = Column(String, nullable=True)

    deployment = relationship("Deployment", back_populates="analysis_periods")

