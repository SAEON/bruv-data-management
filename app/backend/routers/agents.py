from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from db import models, database

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
)


class AgentCreate(BaseModel):
    firstname: Optional[str] = None
    lastname: str
    initials: Optional[str] = None
    title: Optional[str] = None
    jobtitle: Optional[str] = None
    interests: Optional[str] = None
    remarks: Optional[str] = None


@router.get("/")
async def get_agents(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: Session = Depends(database.get_db),
):
    query = db.query(models.Agent)
    if search:
        query = query.filter(
            (models.Agent.lastname.ilike(f"%{search}%"))
            | (models.Agent.firstname.ilike(f"%{search}%"))
            | (models.Agent.jobtitle.ilike(f"%{search}%"))
        )
    total = query.count()
    records = query.order_by(models.Agent.id.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": records}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_agent(
    ag: AgentCreate, db: Session = Depends(database.get_db)
):
    db_ag = models.Agent(**ag.model_dump())
    db.add(db_ag)
    db.commit()
    db.refresh(db_ag)
    return db_ag


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int, db: Session = Depends(database.get_db)):
    ag = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not ag:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(ag)
    db.commit()
    return {"message": "Agent deleted successfully"}
