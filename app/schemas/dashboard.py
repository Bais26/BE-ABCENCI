from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class TodaySummary(BaseModel):
    """Ringkasan kehadiran untuk hari ini."""
    total_karyawan_aktif: int
    total_hadir: int
    total_terlambat: int
    total_alfa: int


class TrendPoint(BaseModel):
    """Satu titik data dalam grafik tren."""
    label: str  # Contoh: "Senin", "W1", "Jan"
    hadir: int
    terlambat: int
    alfa: int

class DashboardResponse(BaseModel):
    """Skema respons utama untuk endpoint dashboard."""
    today_summary: TodaySummary
    attendance_trend: List[TrendPoint]