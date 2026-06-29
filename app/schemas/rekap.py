from pydantic import BaseModel
from typing import Optional, List


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