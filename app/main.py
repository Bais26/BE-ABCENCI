from fastapi import FastAPI
from app.core.config import settings
from app.api.v1 import attendance, auth, schedule, karyawan
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title=settings.APP_NAME)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["Attendance"])
app.include_router(schedule.router, prefix="/api/v1/schedule", tags=["Schedule"])
app.include_router(karyawan.router, prefix="/api/karyawan", tags=["Karyawan"])

@app.get("/")
def root():
    return {"message": "Absensi API running"}
