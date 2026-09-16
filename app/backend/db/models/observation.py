from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.database import Base


class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=True)
    filename = Column(String, nullable=True)
    frame = Column(Integer, nullable=True)
    time_mins = Column(Float, nullable=True)
    period = Column(Text, nullable=True)
    period_time_mins = Column(Float, nullable=True)
    tapereader = Column(String, nullable=True)
    family = Column(String, nullable=True)
    genus = Column(String, nullable=True)
    species = Column(String, nullable=True)
    abundance = Column(Integer, nullable=True)
    abundance_type = Column(String, nullable=True)
    has_fed = Column(Boolean, default=False)
    emobs_data_type = Column(String, nullable=True)

    deployment = relationship("Deployment", back_populates="observations")
