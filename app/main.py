from fastapi import FastAPI
from app.core.config import settings
from app.api.v1 import attendance, auth, schedule, karyawan, gps, rekap, dashboard, division, geocode
from fastapi import APIRouter
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials
import json
import tempfile

DATABASE_URL = os.getenv("DATABASE_URL")

# engine = create_engine(DATABASE_URL)

engine = create_engine(settings.DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# cred = credentials.Certificate(
#     "app/absencbn-firebase-adminsdk-fbsvc-e99bff9d00.json"
# )
if os.getenv("VERCEL"):
    firebase_json = json.loads(os.environ["FIREBASE_CREDENTIALS"])

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(firebase_json, f)
        temp_path = f.name

    cred = credentials.Certificate(temp_path)
else:
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
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["Attendance"])
app.include_router(schedule.router, prefix="/api/v1/schedule", tags=["Schedule"])
app.include_router(karyawan.router, prefix="/api/v1/karyawan", tags=["Karyawan"])
app.include_router(gps.router, prefix="/api/v1/gps", tags=["gps"])
app.include_router(rekap.router, prefix="/api/v1/absens", tags=["Rekap"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(division.router, prefix="/api/v1")
app.include_router(geocode.router, prefix="/api/v1/geocode", tags=["geocode"])

@app.get("/")
def root():
    return {"message": "Absensi API running"}
