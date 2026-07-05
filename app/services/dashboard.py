from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional
from sqlalchemy import func, and_, case
import calendar

from app.models.user import User, UserRole
from app.models.attendance import Attendance, AttendanceStatus
from app.models.karyawan_detail import KaryawanDetail
from app.schemas.dashboard import TodaySummary, TrendPoint
from app.services.rekap import JAKARTA_TZ, count_working_days


def get_today_summary(db: Session) -> TodaySummary:
    """Menghitung ringkasan kehadiran untuk hari ini."""
    today = datetime.now(JAKARTA_TZ).date()

    # 1. Hitung total karyawan aktif dan yang sedang cuti dalam satu query
    karyawan_stats = db.query(
        func.count(User.id),
        func.count(case((KaryawanDetail.status == 'Cuti', User.id)))
    ).select_from(User).outerjoin(User.karyawan_detail).filter(
        User.is_active == True,
        User.role == UserRole.KARYAWAN
    ).one()

    total_karyawan_aktif = karyawan_stats[0]
    karyawan_cuti = karyawan_stats[1]
    
    # 2. Ambil data absensi hari ini untuk menghitung hadir dan terlambat
    attendances_today = db.query(
        Attendance.check_in_status
    ).filter(
        func.date(Attendance.date) == today
    ).all()

    total_hadir = len(attendances_today)
    total_terlambat = sum(1 for att in attendances_today if att.check_in_status == AttendanceStatus.LATE)

    # 3. Hitung alfa (Total karyawan aktif dikurangi yang sudah hadir)
    # Karyawan yang seharusnya masuk (tidak cuti) dikurangi yang sudah hadir
    karyawan_seharusnya_masuk = total_karyawan_aktif - karyawan_cuti
    alfa_count = max(0, karyawan_seharusnya_masuk - total_hadir)

    return TodaySummary(
        total_karyawan_aktif=total_karyawan_aktif,
        total_hadir=total_hadir,
        total_terlambat=total_terlambat,
        total_alfa=alfa_count
    )


def get_attendance_trend(
    db: Session,
    filter_type: str,
    year: int,
    month: Optional[int]
) -> List[TrendPoint]:
    """Menghitung data tren kehadiran (Hadir, Terlambat, Alfa)."""
    
    # Ambil total karyawan aktif dan yang cuti dalam satu query
    karyawan_stats = db.query(
        func.count(User.id),
        func.count(case((KaryawanDetail.status == 'Cuti', User.id)))
    ).select_from(User).outerjoin(User.karyawan_detail).filter(
        User.is_active == True, 
        User.role == UserRole.KARYAWAN
    ).one()

    total_karyawan_aktif = karyawan_stats[0]
    karyawan_cuti = karyawan_stats[1]
    karyawan_seharusnya_masuk = total_karyawan_aktif - karyawan_cuti
    
    trend_data = []

    if filter_type == "week":
        today = datetime.now(JAKARTA_TZ).date()
        start_of_week = today - timedelta(days=today.weekday())
        periods = [(start_of_week + timedelta(days=i)) for i in range(7)]
        labels = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

        for i, period_date in enumerate(periods):
            if period_date.weekday() >= 5: # Lewati akhir pekan
                continue
            
            start_dt = datetime.combine(period_date, datetime.min.time())
            end_dt = datetime.combine(period_date, datetime.max.time())

            # Query hanya kolom yang dibutuhkan
            attendances = db.query(Attendance.check_in_status).filter(
                Attendance.date.between(start_dt, end_dt)
            ).all()
            
            hadir = len(attendances) # Jumlah baris = jumlah hadir
            terlambat = sum(1 for att in attendances if att.check_in_status == AttendanceStatus.LATE)
            alfa = max(0, karyawan_seharusnya_masuk - hadir)

            trend_data.append(TrendPoint(label=labels[i], hadir=hadir, terlambat=terlambat, alfa=alfa))

    elif filter_type == "month":
        num_days = calendar.monthrange(year, month)[1]
        weeks_in_month = (num_days + calendar.weekday(year, month, 1) + 6) // 7
        
        for week_num in range(1, weeks_in_month + 1):
            first_day_of_month = date(year, month, 1)
            start_of_week = first_day_of_month + timedelta(weeks=week_num-1)
            start_of_week -= timedelta(days=start_of_week.weekday())
            end_of_week = start_of_week + timedelta(days=6)

            # Pastikan rentang tetap di dalam bulan yang dipilih
            start_of_week = max(start_of_week, date(year, month, 1))
            end_of_week = min(end_of_week, date(year, month, num_days))

            if start_of_week > end_of_week: continue

            start_dt = datetime.combine(start_of_week, datetime.min.time())
            end_dt = datetime.combine(end_of_week, datetime.max.time())
            
            working_days = count_working_days(start_of_week, end_of_week)
            if working_days == 0: continue

            # Query hanya kolom yang dibutuhkan
            attendances = db.query(Attendance.check_in_status).filter(
                Attendance.date.between(start_dt, end_dt)
            ).all()
            
            hadir = len(attendances) # Jumlah baris = jumlah hadir
            terlambat = sum(1 for att in attendances if att.check_in_status == AttendanceStatus.LATE)
            # Alfa dihitung dari karyawan yang seharusnya masuk
            alfa = max(0, (karyawan_seharusnya_masuk * working_days) - hadir)

            trend_data.append(TrendPoint(label=f"W{week_num}", hadir=hadir, terlambat=terlambat, alfa=alfa))

    elif filter_type == "year":
        labels = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
        for month_num in range(1, 13):
            start_dt = datetime(year, month_num, 1)
            _, num_days = calendar.monthrange(year, month_num)
            end_dt = datetime(year, month_num, num_days, 23, 59, 59)

            working_days = count_working_days(start_dt.date(), end_dt.date())
            if working_days == 0: continue

            # Query hanya kolom yang dibutuhkan
            attendances = db.query(Attendance.check_in_status).filter(
                Attendance.date.between(start_dt, end_dt)
            ).all()
            
            hadir = len(attendances) # Jumlah baris = jumlah hadir
            terlambat = sum(1 for att in attendances if att.check_in_status == AttendanceStatus.LATE)
            # Alfa dihitung dari karyawan yang seharusnya masuk
            alfa = max(0, (karyawan_seharusnya_masuk * working_days) - hadir)

            trend_data.append(TrendPoint(label=labels[month_num-1], hadir=hadir, terlambat=terlambat, alfa=alfa))

    return trend_data