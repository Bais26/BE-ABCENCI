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
from app.models.schedule import WorkSchedule

def get_attendance_stats(
    db: Session,
    start_dt: datetime,
    end_dt: datetime
):
    """
    Menghitung Hadir, Terlambat, Alfa berdasarkan
    Schedule vs Attendance.
    """

    schedules = db.query(
        WorkSchedule.user_id,
        func.date(WorkSchedule.date).label("work_date")
    ).filter(
        WorkSchedule.date.between(start_dt, end_dt)
    ).all()

    schedule_set = {
        (s.user_id, s.work_date)
        for s in schedules
    }

    attendances = db.query(
        Attendance.user_id,
        func.date(Attendance.date).label("work_date"),
        Attendance.check_in_status
    ).filter(
        Attendance.date.between(start_dt, end_dt)
    ).all()

    attendance_set = {
        (a.user_id, a.work_date)
        for a in attendances
    }

    hadir = len({
        (a.user_id, a.work_date)
        for a in attendances
        if a.check_in_status in (
            AttendanceStatus.ONTIME,
            AttendanceStatus.EARLY,
            AttendanceStatus.LATE,
        )
    })

    terlambat = len({
        (a.user_id, a.work_date)
        for a in attendances
        if a.check_in_status == AttendanceStatus.LATE
    })

    alfa = len(schedule_set - attendance_set)

    return hadir, terlambat, alfa

def get_summary(
    db: Session,
    filter_type: str,
    year: int,
    month: int
) -> TodaySummary:

    today = datetime.now(JAKARTA_TZ).date()


    # =========================
    # TOTAL KARYAWAN AKTIF
    # =========================

    total_karyawan_aktif = db.query(
        func.count(User.id)
    ).filter(
        User.is_active == True,
        User.role == UserRole.KARYAWAN
    ).scalar()



    # =========================
    # RANGE FILTER
    # =========================

    if filter_type == "week":

        start_date = today - timedelta(
            days=today.weekday()
        )

        end_date = start_date + timedelta(days=6)


    elif filter_type == "month":

        start_date = date(
            year,
            month,
            1
        )

        last_day = calendar.monthrange(
            year,
            month
        )[1]

        end_date = date(
            year,
            month,
            last_day
        )


    elif filter_type == "year":

        start_date = date(
            year,
            1,
            1
        )

        end_date = date(
            year,
            12,
            31
        )


    else:

        start_date = today
        end_date = today



    start_dt = datetime.combine(
        start_date,
        datetime.min.time()
    )


    end_dt = datetime.combine(
        end_date,
        datetime.max.time()
    )



    # =========================
    # ATTENDANCE
    # =========================

    total_hadir, total_terlambat, total_alfa = get_attendance_stats(
        db,
        start_dt,
        end_dt
    )
    # =========================
    # WORK SCHEDULE WFO WFH
    # =========================

    schedules = db.query(
        WorkSchedule
    ).filter(
        WorkSchedule.date.between(
            start_dt,
            end_dt
        )
    ).all()



    total_wfo = sum(
        1
        for schedule in schedules
        if schedule.work_status.upper() == "WFO"
    )


    total_wfh = sum(
        1
        for schedule in schedules
        if schedule.work_status.upper() == "WFH"
    )

    return TodaySummary(
        total_karyawan_aktif=total_karyawan_aktif,
        total_hadir=total_hadir,
        total_terlambat=total_terlambat,
        total_alfa=total_alfa,
        total_wfo=total_wfo,
        total_wfh=total_wfh
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

    # total_karyawan_aktif = karyawan_stats[0]
    # karyawan_cuti = karyawan_stats[1]
    # karyawan_seharusnya_masuk = total_karyawan_aktif - karyawan_cuti
    
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
            hadir, terlambat, alfa = get_attendance_stats(
                db,
                start_dt,
                end_dt
            )

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
            hadir, terlambat, alfa = get_attendance_stats(
                db,
                start_dt,
                end_dt
            )

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
            hadir, terlambat, alfa = get_attendance_stats(
                db,
                start_dt,
                end_dt
            )

            trend_data.append(TrendPoint(label=labels[month_num-1], hadir=hadir, terlambat=terlambat, alfa=alfa))

    return trend_data

def get_work_mode_trend(
    db: Session,
    filter_type: str = "week",
    year: int = None,
    month: int = None
):

    trend_data = []


    today = datetime.now(JAKARTA_TZ).date()



    def count_work_mode(start_date, end_date):

        schedules = db.query(
            WorkSchedule.work_status
        ).filter(
            WorkSchedule.date.between(
                start_date,
                end_date
            )
        ).all()



        wfo = sum(
            1
            for schedule in schedules
            if schedule.work_status.upper() == "WFO"
        )


        wfh = sum(
            1
            for schedule in schedules
            if schedule.work_status.upper() == "WFH"
        )


        return wfo, wfh



    # =========================
    # WEEK
    # =========================

    if filter_type == "week":


        start_week = today - timedelta(
            days=today.weekday()
        )


        labels = [
            "Senin",
            "Selasa",
            "Rabu",
            "Kamis",
            "Jumat",
            "Sabtu",
            "Minggu"
        ]


        for i in range(7):

            current_date = (
                start_week +
                timedelta(days=i)
            )


            start = datetime.combine(
                current_date,
                datetime.min.time()
            )


            end = datetime.combine(
                current_date,
                datetime.max.time()
            )


            wfo, wfh = count_work_mode(
                start,
                end
            )


            trend_data.append({

                "label": labels[i],

                "wfo": wfo,

                "wfh": wfh

            })




    # =========================
    # MONTH
    # =========================

    elif filter_type == "month":


        if year is None:
            year = today.year


        if month is None:
            month = today.month



        total_days = calendar.monthrange(
            year,
            month
        )[1]



        for day in range(
            1,
            total_days + 1
        ):


            current_date = date(
                year,
                month,
                day
            )


            start = datetime.combine(
                current_date,
                datetime.min.time()
            )


            end = datetime.combine(
                current_date,
                datetime.max.time()
            )


            wfo, wfh = count_work_mode(
                start,
                end
            )


            trend_data.append({

                "label": str(day),

                "wfo": wfo,

                "wfh": wfh

            })




    # =========================
    # YEAR
    # =========================

    elif filter_type == "year":


        if year is None:
            year = today.year



        labels = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "Mei",
            "Jun",
            "Jul",
            "Agu",
            "Sep",
            "Okt",
            "Nov",
            "Des"
        ]



        for month_num in range(1,13):


            start_date = date(
                year,
                month_num,
                1
            )


            last_day = calendar.monthrange(
                year,
                month_num
            )[1]


            end_date = date(
                year,
                month_num,
                last_day
            )



            start = datetime.combine(
                start_date,
                datetime.min.time()
            )


            end = datetime.combine(
                end_date,
                datetime.max.time()
            )



            wfo, wfh = count_work_mode(
                start,
                end
            )



            trend_data.append({

                "label": labels[month_num-1],

                "wfo": wfo,

                "wfh": wfh

            })



    return trend_data