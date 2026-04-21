from pydantic import BaseModel, EmailStr as emailstr
from datetime import datetime  


class AgentBase(BaseModel):
    firstname: str
    lastname: str
    initials: str
    title: str
    email: emailstr

class AgentCreate(AgentBase):
    password: str

class Agent(AgentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


