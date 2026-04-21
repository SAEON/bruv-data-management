from fastapi import FastAPI
from db.database import Base, engine, get_db
from db.models.agent import Agent
from db.schemas import AgentCreate, Agent
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)   

   

@app.get("/")
def read_root():
    return {"message": "Welcome to the Marine Data Management"}

@app.post("/register/", response_model=Agent)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    db_agent = Agent(
        firstname=agent.firstname,
        lastname=agent.lastname,
        initials=agent.initials,
        title=agent.title,
        email=agent.email,
        password=pwd_context.hash(agent.password)
    )

    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return {"message": "Agent created successfully", "agent": db_agent}




