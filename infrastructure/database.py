from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import os

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL","postgresql://nisseya:password123@postgres:5432/benchmark_db")
print(SQLALCHEMY_DATABASE_URL)
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dépendance FastAPI pour récupérer la session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()