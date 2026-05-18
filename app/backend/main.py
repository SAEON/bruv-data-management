from fastapi import FastAPI
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
# from db.models import Agent


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
