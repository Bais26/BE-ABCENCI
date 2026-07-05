from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.utils.security import get_current_admin
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import get_today_summary, get_attendance_trend
from app.services.rekap import JAKARTA_TZ

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/", response_model=DashboardResponse)
def get_dashboard_data(
    filter: str = Query(
        "week",
        regex="^(week|month|year)$",
        description="Filter tren: week, month, year",
    ),
    year: Optional[int] = Query(None, description="Tahun untuk filter month/year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Bulan untuk filter month"),
    db: Session = Depends(get_db),
):
    """
    Mengambil data ringkasan untuk dashboard admin.
    - **today_summary**: Ringkasan kehadiran hari ini (WFO, WFH, Cuti, Alfa).
    - **attendance_trend**: Data tren kehadiran (Hadir, Terlambat, Alfa) berdasarkan filter.
    """
    try:
        now = datetime.now(JAKARTA_TZ)
        if year is None: year = now.year
        if filter == "month" and month is None: month = now.month

        today_summary = get_today_summary(db)
        attendance_trend = get_attendance_trend(db, filter, year, month)

        return DashboardResponse(today_summary=today_summary, attendance_trend=attendance_trend)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))