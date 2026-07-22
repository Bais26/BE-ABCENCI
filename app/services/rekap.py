from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload
from typing import Optional, List, Dict
from datetime import datetime, date, timedelta, time as dt_time
from uuid import UUID
import pytz

from app.models.attendance import Attendance, AttendanceStatus, LocationType
from app.models.user import User
from app.models.karyawan_detail import KaryawanDetail
from app.models.division import Division, SubDivision
from app.models.schedule import OfficeLocation
from app.schemas.rekap import (
    DailyRekapItem,
    RekapSummary,
    KaryawanRekapItem,
)

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")


# ══════════════════════════════════════════════════════════
# DATE HELPERS
# ══════════════════════════════════════════════════════════

def get_date_range(
    filter_type: str,
    year: int,
    month: Optional[int],
    week: Optional[int],
) -> tuple[date, date, str]:
    """
    Kembalikan (start_date, end_date, label_periode).
    end_date tidak melebihi hari ini (WIB).
    """
    today = datetime.now(JAKARTA_TZ).date()

    if filter_type == "week":
        if week is None:
            week = today.isocalendar()[1]
        start = date.fromisocalendar(year, week, 1)
        end = start + timedelta(days=6)
        label = f"{year}-W{week:02d}"

    elif filter_type == "month":
        if month is None:
            month = today.month
        start = date(year, month, 1)
        end = (
            date(year, month + 1, 1) - timedelta(days=1)
            if month < 12
            else date(year, 12, 31)
        )
        label = f"{year}-{month:02d}"

    else:  # year
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        label = str(year)

    return start, min(end, today), label


def count_working_days(start: date, end: date) -> int:
    """Hitung hari kerja Senin–Jumat antara dua tanggal (inklusif)."""
    count, cur = 0, start
    while cur <= end:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return count

# ══════════════════════════════════════════════════════════
# FORMAT HELPERS
# ══════════════════════════════════════════════════════════

def fmt_time_wib(dt: Optional[datetime]) -> Optional[str]:
    """Konversi UTC datetime → string jam WIB "HH:MM"."""
    if dt is None:
        return None
    local = dt.replace(tzinfo=pytz.utc).astimezone(JAKARTA_TZ)
    return local.strftime("%H:%M")

def fmt_duration(minutes: Optional[int]) -> Optional[str]:
    """Konversi menit → string "Xj Ym"."""
    if minutes is None:
        return None
    h, m = divmod(minutes, 60)
    return f"{h}j {m}m"

def day_name_id(d: date) -> str:
    """Nama hari dalam Bahasa Indonesia."""
    DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    return DAYS[d.weekday()]

# ══════════════════════════════════════════════════════════
# OFFICE MAP
# ══════════════════════════════════════════════════════════

def get_office_map(db: Session, attendances: List[Attendance]) -> Dict:
    """Ambil semua nama kantor sekaligus (1 query)."""
    ids = {a.office_location_id for a in attendances if a.office_location_id}
    if not ids:
        return {}
    return {
        o.id: o.name
        for o in db.query(OfficeLocation).filter(OfficeLocation.id.in_(ids)).all()
    }

# ══════════════════════════════════════════════════════════
# BUILD SUMMARY
# ══════════════════════════════════════════════════════════

def build_summary(
    attendances: List[Attendance],
    start: date,
    end: date,
    label: str,
    filter_type: str,
) -> RekapSummary:

    total_hari_kerja = count_working_days(start, end)

    # ==========================
    # STATUS KEHADIRAN
    # ==========================

    # ONTIME, LATE, EARLY tetap dianggap hadir
    total_hadir = sum(
        1
        for a in attendances
        if a.check_in_status in [
            AttendanceStatus.ONTIME,
            AttendanceStatus.LATE,
            AttendanceStatus.EARLY
        ]
    )

    # ABSENT = Alfa
    total_alfa = sum(
        1
        for a in attendances
        if a.check_in_status == AttendanceStatus.ABSENT
    )

    total_wfo = sum(
        1
        for a in attendances
        if a.work_status == LocationType.WFO
    )

    total_wfh = sum(
        1
        for a in attendances
        if a.work_status == LocationType.WFH
    )

    total_ontime = sum(
        1
        for a in attendances
        if a.check_in_status == AttendanceStatus.ONTIME
    )

    total_terlambat = sum(
        1
        for a in attendances
        if a.check_in_status == AttendanceStatus.LATE
    )

    total_pulang_awal = sum(
        1
        for a in attendances
        if a.check_out_status == AttendanceStatus.EARLY
    )

    # ==========================
    # DURASI KERJA
    # ==========================
    total_menit = sum(
        a.work_duration_minutes
        for a in attendances
        if a.work_duration_minutes is not None
    )

    completed = [
        a
        for a in attendances
        if a.work_duration_minutes is not None
    ]

    rata = (
        int(total_menit / len(completed))
        if completed
        else None
    )

    attendance_rate = (
        round(
            (total_hadir / len(attendances)) * 100,
            2
        )
        if attendances
        else 0.0
    )

    return RekapSummary(
        periode=label,
        filter_type=filter_type,
        total_hari_kerja=total_hari_kerja,
        total_hadir=total_hadir,
        total_alfa=total_alfa,
        total_wfo=total_wfo,
        total_wfh=total_wfh,
        total_ontime=total_ontime,
        total_terlambat=total_terlambat,
        total_pulang_awal=total_pulang_awal,
        total_menit_kerja=total_menit,
        rata_rata_menit_kerja=rata,
        attendance_rate=attendance_rate,
    )


# ══════════════════════════════════════════════════════════
# BUILD DAILY ITEM
# ══════════════════════════════════════════════════════════

def to_daily_item(att: Attendance, office_name: Optional[str]) -> DailyRekapItem:
    att_date = att.date.date() if isinstance(att.date, datetime) else att.date
    return DailyRekapItem(
        tanggal=att_date.isoformat(),
        hari=day_name_id(att_date),
        check_in_time=fmt_time_wib(att.check_in_time),
        check_out_time=fmt_time_wib(att.check_out_time),
        check_in_status=att.check_in_status.value if att.check_in_status else None,
        check_out_status=att.check_out_status.value if att.check_out_status else None,
        work_status=att.work_status.value if att.work_status else None,
        office_location_name=office_name,
        durasi_kerja=fmt_duration(att.work_duration_minutes),
        is_validated=att.is_validated,
    )


# ══════════════════════════════════════════════════════════
# QUERY USERS (untuk admin)
# ══════════════════════════════════════════════════════════

def query_users(
    db: Session,
    user_id: Optional[str] = None,
    nama: Optional[str] = None,
    email: Optional[str] = None,
    divisi: Optional[str] = None,
    subdivisi: Optional[str] = None,
    posisi: Optional[str] = None,
) -> List[User]:
    """
    Query User dengan filter opsional.
    Eager-load karyawan_detail -> subdivision -> division untuk menghindari N+1.
    """
    q = (
        db.query(User)
        .outerjoin(User.karyawan_detail)
        .outerjoin(KaryawanDetail.subdivision)
        .outerjoin(SubDivision.division)
        .filter(User.is_active == True)
        .options(
            joinedload(User.karyawan_detail)
            .joinedload(KaryawanDetail.subdivision)
            .joinedload(SubDivision.division)
        )
    )

    if user_id:
        q = q.filter(User.id == UUID(user_id))
    if nama:
        q = q.filter(User.full_name.ilike(f"%{nama}%"))
    if email:
        q = q.filter(User.email.ilike(f"%{email}%"))
    if divisi:
        q = q.filter(Division.name.ilike(f"%{divisi}%"))
    if subdivisi:
        q = q.filter(SubDivision.name.ilike(f"%{subdivisi}%"))
    if posisi:
        q = q.filter(KaryawanDetail.posisi.ilike(f"%{posisi}%"))

    return q # Kembalikan objek query, bukan hasilnya


# ══════════════════════════════════════════════════════════
# BUILD KARYAWAN REKAP ITEM (untuk admin)
# ══════════════════════════════════════════════════════════

def build_karyawan_item(
    user: User,
    attendances: List[Attendance],
    total_hari_kerja: int,
) -> KaryawanRekapItem:
    detail = user.karyawan_detail
    divisi_name = None
    subdivisi_name = None
    if detail and detail.subdivision:
        subdivisi_name = detail.subdivision.name
        if detail.subdivision.division:
            divisi_name = detail.subdivision.division.name
    total_hadir = sum(
        1
        for a in attendances
        if a.check_in_status in [
            AttendanceStatus.ONTIME,
            AttendanceStatus.LATE,
            AttendanceStatus.EARLY
        ]
    )

    total_alfa = sum(
        1
        for a in attendances
        if a.check_in_status == AttendanceStatus.ABSENT
    )
    wfo = sum(1 for a in attendances if a.work_status == LocationType.WFO)
    wfh = sum(1 for a in attendances if a.work_status == LocationType.WFH)
    ontime = sum(1 for a in attendances if a.check_in_status == AttendanceStatus.ONTIME)
    terlambat = sum(1 for a in attendances if a.check_in_status == AttendanceStatus.LATE)
    pulang_awal = sum(1 for a in attendances if a.check_out_status == AttendanceStatus.EARLY)
    total_menit = sum(
        a.work_duration_minutes for a in attendances if a.work_duration_minutes is not None
    )
    completed = [a for a in attendances if a.work_duration_minutes is not None]
    rata = int(total_menit / len(completed)) if completed else None
    rate = (
        round(
            (total_hadir / len(attendances)) * 100,
            2
        )
        if attendances
        else 0.0
    )

    return KaryawanRekapItem(
        user_id=str(user.id),
        nama_lengkap=user.full_name,
        email=user.email,
        posisi=detail.posisi if detail else None,
        divisi=divisi_name,
        subdivisi=subdivisi_name,
        total_hadir=total_hadir,
        total_alfa=total_alfa,
        total_wfo=wfo,
        total_wfh=wfh,
        total_ontime=ontime,
        total_terlambat=terlambat,
        total_pulang_awal=pulang_awal,
        total_menit_kerja=total_menit,
        rata_rata_menit_kerja=rata,
        attendance_rate=rate,
    )