from pydantic import BaseModel
from typing import List


class TodaySummary(BaseModel):
    total_karyawan_aktif: int
    total_hadir: int
    total_terlambat: int
    total_alfa: int
    total_wfo: int
    total_wfh: int


class TrendPoint(BaseModel):
    label: str
    hadir: int
    terlambat: int
    alfa: int


class WorkModeTrend(BaseModel):
    label: str
    wfo: int
    wfh: int


class DashboardResponse(BaseModel):
    today_summary: TodaySummary
    attendance_trend: List[TrendPoint]
    work_mode_trend: List[WorkModeTrend]