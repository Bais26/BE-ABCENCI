from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.gps import validate_location

router = APIRouter()

@router.post("/check-in")
def check_in(
    latitude: float,
    longitude: float,
    db: Session = Depends(get_db)
):
    valid = validate_location(latitude, longitude)
    if not valid:
        return {"status": "failed", "message": "Di luar area absensi"}

    return {"status": "success", "message": "Absensi berhasil"}
