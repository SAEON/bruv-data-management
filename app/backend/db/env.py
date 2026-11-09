import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://marinedata:marinedata@localhost:5432/marinedata"
)
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here")
ACCESS_TOKEN_EXPIRE_MINUTES = 30
