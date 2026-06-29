# app/schemas/attendance.py - PERBAIKAN
from pydantic import BaseModel, Field, ConfigDict  # Ganti import
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid

class AttendanceStatus(str, Enum):
    ONTIME = "ontime"
    LATE = "late"
    EARLY = "early"
    ABSENT = "absent"

class LocationType(str, Enum):
    WFO = "wfo"
    WFH = "wfh"

class CheckInRequest(BaseModel):
    latitude: Optional[float] = Field(None, description="Latitude for WFO check-in")
    longitude: Optional[float] = Field(None, description="Longitude for WFO check-in")
    date: Optional[str] = Field(None, description="Custom date (YYYY-MM-DD format)")
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # TAMBAHKAN INI
        from_attributes=True
    )

class CheckOutRequest(BaseModel):
    latitude: Optional[float] = Field(None, description="Latitude for WFO check-out")
    longitude: Optional[float] = Field(None, description="Longitude for WFO check-out")
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

class AttendanceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    date: datetime
    check_in_time: Optional[datetime] = None
    check_in_status: Optional[AttendanceStatus] = None
    check_in_location_type: Optional[LocationType] = None
    check_out_time: Optional[datetime] = None
    check_out_status: Optional[AttendanceStatus] = None
    work_duration_minutes: Optional[int] = None
    work_status: LocationType
    office_location_name: Optional[str] = None
    office_location_id: Optional[uuid.UUID] = None
    is_validated: bool
    validation_note: Optional[str] = None
    created_at: datetime
    validation_details: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )

class AttendanceListResponse(BaseModel):
    items: List[AttendanceResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

class AttendanceSummary(BaseModel):
    month: int
    year: int
    total_days: int
    working_days: int
    wfo_days: int
    wfh_days: int
    attendance_rate: float
    ontime_checkins: int
    late_checkins: int
    ontime_checkouts: int
    early_checkouts: int
    avg_checkin_time: Optional[str] = None
    last_attendance: Optional[Dict[str, Any]] = None
    total_work_minutes: int = 0
    avg_work_minutes: Optional[int] = None
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

class AttendanceStats(BaseModel):
    total_attendances: int
    current_month_count: int
    wfo_percentage: float
    wfh_percentage: float
    ontime_percentage: float
    late_percentage: float
    current_streak: int
    longest_streak: int
    first_attendance_date: Optional[date] = None
    most_frequent_office: Optional[Dict[str, Any]] = None
    total_work_minutes_this_month: int = 0
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

class DailyRekapItem(BaseModel):
    """Detail absensi per hari – untuk karyawan sendiri."""
    tanggal: str                          # "2025-06-12"
    hari: str                             # "Kamis"
    check_in_time: Optional[str]          # "09:05" (WIB)
    check_out_time: Optional[str]         # "17:10" (WIB)
    check_in_status: Optional[str]        # ontime / late
    check_out_status: Optional[str]       # ontime / early
    work_status: Optional[str]            # wfo / wfh
    office_location_name: Optional[str]
    durasi_kerja: Optional[str]           # "7j 30m"
    is_validated: Optional[bool]
 
    class Config:
        from_attributes = True
 
 
class RekapSummary(BaseModel):
    """Ringkasan statistik satu periode."""
    periode: str
    filter_type: str                      # week / month / year
    total_hari_kerja: int
    total_hadir: int
    total_absen: int
    total_wfo: int
    total_wfh: int
    total_ontime: int
    total_terlambat: int
    total_pulang_awal: int
    total_menit_kerja: int
    rata_rata_menit_kerja: Optional[int]
    attendance_rate: float                # persen
 
 
class MyRekapResponse(BaseModel):
    summary: RekapSummary
    detail: List[DailyRekapItem]
 
 
class KaryawanRekapItem(BaseModel):
    """Satu baris rekap per karyawan – untuk admin."""
    user_id: str
    nama_lengkap: str
    email: str
    posisi: Optional[str]
    divisi: Optional[str]
    total_hadir: int
    total_absen: int
    total_wfo: int
    total_wfh: int
    total_ontime: int
    total_terlambat: int
    total_pulang_awal: int
    total_menit_kerja: int
    rata_rata_menit_kerja: Optional[int]
    attendance_rate: float
 
 
class AdminRekapResponse(BaseModel):
    summary: RekapSummary
    karyawan: List[KaryawanRekapItem]
    total_karyawan: int
    page: int
    limit: int
    total_pages: int
