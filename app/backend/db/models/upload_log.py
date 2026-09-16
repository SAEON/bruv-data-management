from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from db.database import Base


class UploadLog(Base):
    __tablename__ = "upload_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    sheet_name = Column(String, nullable=True)
    entity_type = Column(String, nullable=False)
    total_rows = Column(Integer, default=0)
    inserted_rows = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)
    status = Column(String, nullable=False)  # 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED'
    error_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
