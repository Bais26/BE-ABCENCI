from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.utils.security import get_current_admin
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import (
    get_summary,
    get_attendance_trend,
    get_work_mode_trend
)
from app.services.rekap import JAKARTA_TZ


router = APIRouter(
    dependencies=[Depends(get_current_admin)]
)


@router.get("/", response_model=DashboardResponse)
def get_dashboard_data(

    filter: str = Query(
        "week",
        pattern="^(week|month|year)$",
        description="Filter attendance: week, month, year"
    ),

    mode_filter: str = Query(
        "week",
        pattern="^(week|month|year)$",
        description="Filter WFO/WFH: week, month, year"
    ),


    year: Optional[int] = Query(
        None,
        description="Tahun"
    ),


    month: Optional[int] = Query(
        None,
        ge=1,
        le=12,
        description="Bulan"
    ),


    db: Session = Depends(get_db)

):


    try:

        now = datetime.now(JAKARTA_TZ)


        if year is None:
            year = now.year


        if month is None:
            month = now.month



        today_summary = get_summary(
            db,
            filter,
            year,
            month
        )



        attendance_trend = get_attendance_trend(
            db,
            filter,
            year,
            month
        )



        work_mode_trend = get_work_mode_trend(
            db,
            mode_filter,
            year,
            month
        )



        return DashboardResponse(

            today_summary=today_summary,

            attendance_trend=attendance_trend,

            work_mode_trend=work_mode_trend

        )


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )