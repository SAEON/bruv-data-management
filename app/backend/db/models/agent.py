from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    title = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    research_interests = Column(Text, nullable=True)
    email = Column(String, nullable=True)
    remarks = Column(Text, nullable=True)

    owner = relationship("User")
