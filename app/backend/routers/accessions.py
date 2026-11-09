from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from db import models, database

router = APIRouter(
    prefix="/accessions",
    tags=["accessions"],
)


class AccessionCreate(BaseModel):
    accessionnumber: str
    accessioncondition: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None
    totalvalue: Optional[float] = None
    dateaccessioned: Optional[datetime] = None


@router.get("/")
async def get_accessions(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(database.get_db),
):
    query = db.query(models.Accession)
    if search:
        query = query.filter(
            (models.Accession.accessionnumber.ilike(f"%{search}%"))
            | (models.Accession.type.ilike(f"%{search}%"))
            | (models.Accession.remark.ilike(f"%{search}%"))
        )
    total = query.count()
    records = query.order_by(models.Accession.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": records}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_accession(
    acc: AccessionCreate, db: Session = Depends(database.get_db)
):
    db_acc = models.Accession(**acc.model_dump())
    db.add(db_acc)
    db.commit()
    db.refresh(db_acc)
    return db_acc


@router.delete("/{accession_id}")
async def delete_accession(accession_id: int, db: Session = Depends(database.get_db)):
    acc = db.query(models.Accession).filter(models.Accession.id == accession_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Accession not found")
    db.delete(acc)
    db.commit()
    return {"message": "Accession deleted successfully"}
