from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from db import models, database

router = APIRouter(
    prefix="/observations",
    tags=["observations"],
)


class ObservationCreate(BaseModel):
    survey_code: str
    species_name: str
    location: Optional[str] = None
    site_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    depth_m: Optional[float] = None
    video_filename: Optional[str] = None
    common_name: Optional[str] = None
    family: Optional[str] = None
    count: Optional[int] = 1
    max_n: Optional[int] = 1
    habitat_type: Optional[str] = None
    date_recorded: Optional[datetime] = None
    remarks: Optional[str] = None


@router.get("/")
async def get_observations(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(database.get_db),
):
    query = db.query(models.Observation)
    if search:
        query = query.filter(
            (models.Observation.survey_code.ilike(f"%{search}%"))
            | (models.Observation.species_name.ilike(f"%{search}%"))
            | (models.Observation.common_name.ilike(f"%{search}%"))
            | (models.Observation.location.ilike(f"%{search}%"))
        )
    total = query.count()
    records = query.order_by(models.Observation.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": records}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_observation(
    obs: ObservationCreate, db: Session = Depends(database.get_db)
):
    db_obs = models.Observation(**obs.model_dump())
    db.add(db_obs)
    db.commit()
    db.refresh(db_obs)
    return db_obs


@router.delete("/{obs_id}")
async def delete_observation(obs_id: int, db: Session = Depends(database.get_db)):
    obs = db.query(models.Observation).filter(models.Observation.id == obs_id).first()
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")
    db.delete(obs)
    db.commit()
    return {"message": "Observation deleted successfully"}
