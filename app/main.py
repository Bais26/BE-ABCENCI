from fastapi import FastAPI
from app.core.config import settings
from app.api.v1 import attendance, auth, schedule, karyawan, gps, rekap
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials

DATABASE_URL = os.getenv("DATABASE_URL")

# engine = create_engine(DATABASE_URL)

engine = create_engine(settings.DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
cred = credentials.Certificate(
    "app/absencbn-firebase-adminsdk-fbsvc-e99bff9d00.json"
)
# Pastikan firebase hanya diinisialisasi sekali
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

app = FastAPI(
    title=settings.APP_NAME,
    # Konfigurasi ini memberitahu Swagger UI untuk tidak menggunakan client_id/secret
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://your-frontend-domain.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["Attendance"])
app.include_router(schedule.router, prefix="/api/v1", tags=["Schedule"])
app.include_router(karyawan.router, prefix="/api/v1", tags=["Karyawan"])
app.include_router(gps.router, prefix="/api/v1", tags=["gps"])
app.include_router(rekap.router, prefix="/api/v1/absens", tags=["Rekap"])

@app.get("/")
def root():
    return {"message": "Absensi API running"}
