"""Field-trip day-sheet model."""

from sqlalchemy import Column, Date, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from db.database import Base


class DaySheet(Base):
    __tablename__ = "day_sheets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fieldtrip_id = Column(Integer, ForeignKey("fieldtrips.id"), nullable=False)
    date = Column(Date, nullable=True)
    planned_tasks = Column(Text, nullable=True)
    sites_visited = Column(Text, nullable=True)
    sites_completed = Column(Text, nullable=True)
    wind = Column(Text, nullable=True)
    sea_conditions = Column(Text, nullable=True)
    cloud_pct = Column(Integer, nullable=True)
    rain = Column(Text, nullable=True)
    surface_visibility = Column(Text, nullable=True)
    surface_water_conditions = Column(Text, nullable=True)
    depth = Column(Integer, nullable=True)
    swell = Column(Text, nullable=True)
    difficulties_encountered = Column(Text, nullable=True)
    issues_to_be_discussed = Column(Text, nullable=True)
    advice_received = Column(Text, nullable=True)
    plan_for_next_day = Column(Text, nullable=True)

    field_trip = relationship("FieldTrip", back_populates="day_sheets")