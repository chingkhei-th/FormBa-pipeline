from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

try:
    engine = create_engine(DATABASE_URL, echo=True)  # Added echo=True for debugging
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    print(f"Database connection error: {e}")
    raise


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
