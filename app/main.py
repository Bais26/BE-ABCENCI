from fastapi import FastAPI
from app.core.config import settings
from app.api.v1 import attendance, auth, schedule, karyawan

app = FastAPI(title=settings.APP_NAME)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["Attendance"])
app.include_router(schedule.router, prefix="/api/v1/schedule", tags=["Schedule"])
app.include_router(karyawan.router, prefix="/api/karyawan", tags=["Karyawan"])

@app.get("/")
def root():
    return {"message": "Absensi API running"}
