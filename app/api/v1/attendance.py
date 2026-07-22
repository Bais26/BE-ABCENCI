from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, date, timedelta, time as dt_time
from uuid import UUID
import uuid

from app.core.database import get_db
from app.services.gps import GPSValidationService
from app.utils.security import get_current_user, get_current_admin
from app.models.user import User, UserRole
from app.models.attendance import Attendance, AttendanceStatus, LocationType
from app.models.schedule import WorkSchedule, OfficeLocation
from app.schemas.attendance import (
    CheckInRequest, CheckOutRequest,
    AttendanceResponse, AttendanceListResponse,
    AttendanceSummary, AttendanceStats
)
from datetime import timezone
import pytz

router = APIRouter()

@router.post("/check-in", response_model=AttendanceResponse)
async def check_in(
    request: CheckInRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check-in attendance with GPS validation for WFO
    
    Logic:
    - WFO: Requires GPS validation within office radius
    - WFH: No GPS validation required
    """
    
    try:
        # Get today's date (or specified date)
        today = request.date or datetime.utcnow().date()
        
        # Get today's work schedule
        schedule = db.query(WorkSchedule).filter(
            WorkSchedule.user_id == current_user.id,
            WorkSchedule.date >= datetime.combine(today, dt_time.min),
            WorkSchedule.date <= datetime.combine(today, dt_time.max),

        ).first()
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak ada jadwal kerja untuk hari ini"
            )
        
        # Check if already checked in today
        existing_attendance = db.query(Attendance).filter(
            Attendance.user_id == current_user.id,
            Attendance.date >= datetime.combine(today, datetime.min.time()),
            Attendance.date <= datetime.combine(today, datetime.max.time())
        ).first()
        
        if existing_attendance and existing_attendance.check_in_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sudah check-in hari ini"
            )
        
        # Validate location based on work status
        is_valid_location = False
        validation_details = {}
        office_location = None
        
        if str(schedule.work_status).upper() == "WFO":
            # WFO requires GPS validation
            if not schedule.office_location_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Lokasi kantor tidak ditentukan untuk jadwal WFO"
                )
            
            if request.latitude is None or request.longitude is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Koordinat GPS diperlukan untuk check-in WFO"
                )
            
            # Get office location
            office_location = db.query(OfficeLocation).filter(
                OfficeLocation.id == schedule.office_location_id,
                OfficeLocation.is_active == True
            ).first()
            
            if not office_location:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Lokasi kantor tidak ditemukan atau tidak aktif"
                )
            
            # Validate GPS location
            is_valid_location, distance, details = GPSValidationService.is_within_radius(
                request.latitude,
                request.longitude,
                office_location.latitude,
                office_location.longitude,
                office_location.radius,
                use_geopy=False  # Use Haversine for speed
            )
            
            validation_details = details
            
            if not is_valid_location:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Anda berada di luar radius {office_location.radius}m dari {office_location.name}. Jarak: {distance:.1f}m"
                )
        
        elif schedule.work_status.upper() == "WFH":
            # No GPS validation required for WFH
            is_valid_location = True
            validation_details = {
                "note": "WFH - No GPS validation required",
                "validation_type": "WFH"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Work status tidak valid: {schedule.work_status}"
            )
        # Determine check-in status (ontime/late)
        check_in_time = datetime.utcnow()
        check_in_status = AttendanceStatus.ONTIME
        
        # Calculate if late (assuming work starts at 9:00 AM)
        # work_start_time = datetime.combine(today, datetime.strptime("09:00", "%H:%M").time())
        # if check_in_time.time() > work_start_time.time():
        #     check_in_status = AttendanceStatus.LATE
            
        #     # Calculate minutes late
        #     time_difference = check_in_time - work_start_time
        #     minutes_late = time_difference.total_seconds() / 60
            
        #     validation_details.update({
        #         "minutes_late": round(minutes_late, 1),
        #         "work_start_time": work_start_time.isoformat()
        #     })
        
        JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

        check_in_time_local = datetime.now(JAKARTA_TZ)
        work_start = check_in_time_local.replace(hour=9, minute=0, second=0, microsecond=0)

        check_in_status = AttendanceStatus.ONTIME
        if check_in_time_local > work_start:
            check_in_status = AttendanceStatus.LATE
            minutes_late = (check_in_time_local - work_start).total_seconds() / 60
            validation_details["minutes_late"] = round(minutes_late, 1)

        check_in_time_utc = check_in_time_local.astimezone(timezone.utc).replace(tzinfo=None)

        # Create attendance record
        attendance = Attendance(
            user_id=current_user.id,
            date=datetime.utcnow(),
            check_in_time=check_in_time,
            check_in_lat=request.latitude if schedule.work_status.upper() == "WFO" else None,
            check_in_lng=request.longitude if schedule.work_status.upper() == "WFO" else None,
            is_validated=(schedule.work_status.upper() == "WFH"),
            check_in_status=check_in_status,
            check_in_location_type=schedule.work_status,
            work_status=schedule.work_status,
            office_location_id=schedule.office_location_id,
            # is_validated=(schedule.work_status == LocationType.WFH),  # Auto-validate WFH
            validation_note=validation_details.get("note", "Validated by system")
        )
        
        db.add(attendance)
        db.commit()
        db.refresh(attendance)
        
        # Prepare response
        response_data = AttendanceResponse(
            **attendance.__dict__,
            office_location_name=office_location.name if office_location else None,
            validation_details=validation_details
        )
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Check-in gagal: {str(e)}"
        )

@router.post("/check-out", response_model=AttendanceResponse)
async def check_out(
    request: CheckOutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check-out attendance
    
    Note: For WFO, GPS is recommended but not required for check-out
    """
    
    try:
        today = datetime.utcnow().date()
        
        # Get today's attendance
        attendance = db.query(Attendance).filter(
            Attendance.user_id == current_user.id,
            Attendance.date >= datetime.combine(today, datetime.min.time()),
            Attendance.date <= datetime.combine(today, datetime.max.time())
        ).first()
        
        if not attendance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak ada record check-in untuk hari ini"
            )
        
        if attendance.check_out_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sudah check-out hari ini"
            )
        
        # Determine check-out status (ontime/early)
        JAKARTA_TZ = pytz.timezone("Asia/Jakarta")

        check_out_time_local = datetime.now(JAKARTA_TZ)
        work_end = check_out_time_local.replace(hour=17, minute=0, second=0, microsecond=0)

        check_out_status = AttendanceStatus.ONTIME
        minutes_early = 0

        if check_out_time_local < work_end:
            check_out_status = AttendanceStatus.EARLY
            minutes_early = (work_end - check_out_time_local).total_seconds() / 60

        # Simpan ke DB dalam UTC
        check_out_time_utc = check_out_time_local.astimezone(timezone.utc).replace(tzinfo=None)

        # Lalu update attendance
        attendance.check_out_time = check_out_time_utc
        attendance.check_out_status = check_out_status
        
        if attendance.check_in_time:
            duration = check_out_time_utc - attendance.check_in_time
            attendance.work_duration_minutes = max(0, int(duration.total_seconds() / 60))
        # For WFO, update check-out GPS if provided
        if attendance.work_status == LocationType.WFO:
            if request.latitude and request.longitude:
                attendance.check_out_lat = request.latitude
                attendance.check_out_lng = request.longitude
        
        db.commit()
        db.refresh(attendance)
        
        # Get office location name
        office_location_name = None
        if attendance.office_location_id:
            office = db.query(OfficeLocation).filter(
                OfficeLocation.id == attendance.office_location_id
            ).first()
            office_location_name = office.name if office else None
        
        response_data = AttendanceResponse(
            **attendance.__dict__,
            office_location_name=office_location_name
        )
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Check-out gagal: {str(e)}"
        )

@router.get("/my-attendance", response_model=AttendanceListResponse)
async def get_my_attendance(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(30, ge=1, le=100, description="Number of records"),
    page: int = Query(1, ge=1, description="Page number"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get attendance history for current user with pagination
    """
    
    try:
        query = db.query(Attendance).filter(Attendance.user_id == current_user.id)
        
        # Apply date filters
        if start_date:
            query = query.filter(Attendance.date >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(Attendance.date <= datetime.combine(end_date, datetime.max.time()))
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        attendances = query.order_by(Attendance.date.desc()).offset(offset).limit(limit).all()
        
        # Get office location names
        attendance_list = []
        for att in attendances:
            office_location_name = None
            if att.office_location_id:
                office = db.query(OfficeLocation).filter(
                    OfficeLocation.id == att.office_location_id
                ).first()
                office_location_name = office.name if office else None
            
            attendance_list.append(
                AttendanceResponse(
                    **att.__dict__,
                    office_location_name=office_location_name
                )
            )
        
        return AttendanceListResponse(
            items=attendance_list,
            total=total_count,
            page=page,
            limit=limit,
            total_pages=(total_count + limit - 1) // limit,
            has_next=page < ((total_count + limit - 1) // limit),
            has_prev=page > 1
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil data attendance: {str(e)}"
        )

@router.get("/today")
async def get_today_attendance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get today's attendance status
    """
    
    try:
        today = datetime.utcnow().date()
        
        attendance = db.query(Attendance).filter(
            Attendance.user_id == current_user.id,
            Attendance.date >= datetime.combine(today, datetime.min.time()),
            Attendance.date <= datetime.combine(today, datetime.max.time())
        ).first()
        
        # Get today's schedule
        schedule = db.query(WorkSchedule).filter(
            WorkSchedule.user_id == current_user.id,
            WorkSchedule.date >= datetime.combine(today, dt_time.min),
            WorkSchedule.date <= datetime.combine(today, dt_time.max),

        ).first()
        
        response_data = {
            "date": today.isoformat(),
            "has_checked_in": attendance is not None and attendance.check_in_time is not None,
            "has_checked_out": attendance is not None and attendance.check_out_time is not None,
            "work_status": schedule.work_status if schedule else None,
            "schedule_today": schedule is not None,
            "current_time": datetime.utcnow().isoformat()
        }
        
        if attendance:
            response_data.update({
                "check_in_time": attendance.check_in_time.isoformat() if attendance.check_in_time else None,
                "check_out_time": attendance.check_out_time.isoformat() if attendance.check_out_time else None,
                "check_in_status": attendance.check_in_status,
                "check_out_status": attendance.check_out_status,
                "work_status": attendance.work_status
            })
        
        if schedule and schedule.office_location_id:
            office = db.query(OfficeLocation).filter(
                OfficeLocation.id == schedule.office_location_id
            ).first()
            if office:
                response_data["office_location"] = {
                    "name": office.name,
                    "address": office.address,
                    "radius": office.radius
                }
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil data hari ini: {str(e)}"
        )

@router.get("/summary", response_model=AttendanceSummary)
async def get_attendance_summary(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    year: Optional[int] = Query(None, ge=2000, le=2100, description="Year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get attendance summary for current user
    """
    
    try:
        # Default to current month
        if not month:
            month = datetime.utcnow().month
        if not year:
            year = datetime.utcnow().year
        
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # Get all attendances for the month
        attendances = db.query(Attendance).filter(
            Attendance.user_id == current_user.id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()
        
        # Calculate statistics
        total_days = len(attendances)
        wfo_days = sum(1 for a in attendances if a.work_status == LocationType.WFO)
        wfh_days = sum(1 for a in attendances if a.work_status == LocationType.WFH)
        
        # Attendance status counts
        ontime_checkins = sum(1 for a in attendances if a.check_in_status == AttendanceStatus.ONTIME)
        late_checkins = sum(1 for a in attendances if a.check_in_status == AttendanceStatus.LATE)
        
        ontime_checkouts = sum(1 for a in attendances if a.check_out_status == AttendanceStatus.ONTIME)
        early_checkouts = sum(1 for a in attendances if a.check_out_status == AttendanceStatus.EARLY)
        
        # Calculate averages
        avg_checkin_time = None
        avg_checkout_time = None
        
        if attendances:
            # Average check-in time
            total_seconds = sum(
                (a.check_in_time.hour * 3600 + a.check_in_time.minute * 60 + a.check_in_time.second)
                for a in attendances if a.check_in_time
            )
            avg_checkin_seconds = total_seconds / len([a for a in attendances if a.check_in_time])
            avg_checkin_hour = int(avg_checkin_seconds // 3600)
            avg_checkin_minute = int((avg_checkin_seconds % 3600) // 60)
            avg_checkin_time = f"{avg_checkin_hour:02d}:{avg_checkin_minute:02d}"
        
        # Working days in month (excluding weekends)
        working_days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Monday to Friday
                working_days += 1
            current += timedelta(days=1)
        
        attendance_rate = (total_days / working_days * 100) if working_days > 0 else 0
        
        # Get last attendance
        last_attendance = None
        if attendances:
            latest = max(attendances, key=lambda x: x.date)
            office_name = None
            if latest.office_location_id:
                office = db.query(OfficeLocation).filter(
                    OfficeLocation.id == latest.office_location_id
                ).first()
                office_name = office.name if office else None
            
            last_attendance = {
                "date": latest.date,
                "check_in_time": latest.check_in_time,
                "check_out_time": latest.check_out_time,
                "work_status": latest.work_status,
                "office_location": office_name
            }
            # Tambah setelah kalkulasi statistik yang sudah ada
            total_work_minutes = sum(
                a.work_duration_minutes for a in attendances
                if a.work_duration_minutes is not None
            )

            completed_days = len([a for a in attendances if a.work_duration_minutes is not None])
            avg_work_minutes = int(total_work_minutes / completed_days) if completed_days > 0 else None

            return AttendanceSummary(
                month=month,
                year=year,
                total_days=total_days,
                working_days=working_days,
                wfo_days=wfo_days,
                wfh_days=wfh_days,
                attendance_rate=round(attendance_rate, 2),
                ontime_checkins=ontime_checkins,
                late_checkins=late_checkins,
                ontime_checkouts=ontime_checkouts,
                early_checkouts=early_checkouts,
                avg_checkin_time=avg_checkin_time,
                last_attendance=last_attendance,
                total_work_minutes=total_work_minutes,       # ── TAMBAH
                avg_work_minutes=avg_work_minutes,           # ── TAMBAH
            )
        # return AttendanceSummary(
        #     month=month,
        #     year=year,
        #     total_days=total_days,
        #     working_days=working_days,
        #     wfo_days=wfo_days,
        #     wfh_days=wfh_days,
        #     attendance_rate=round(attendance_rate, 2),
        #     ontime_checkins=ontime_checkins,
        #     late_checkins=late_checkins,
        #     ontime_checkouts=ontime_checkouts,
        #     early_checkouts=early_checkouts,
        #     avg_checkin_time=avg_checkin_time,
        #     last_attendance=last_attendance
        # )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membuat summary: {str(e)}"
        )

@router.get("/stats", response_model=AttendanceStats)
async def get_attendance_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive attendance statistics
    """
    
    try:
        # Current month stats
        current_month = datetime.utcnow().month
        current_year = datetime.utcnow().year
        
        start_date = datetime(current_year, current_month, 1)
        if current_month == 12:
            end_date = datetime(current_year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(current_year, current_month + 1, 1) - timedelta(days=1)
        
        # Current month attendances
        current_month_attendances = db.query(Attendance).filter(
            Attendance.user_id == current_user.id,
            Attendance.date >= start_date,
            Attendance.date <= end_date
        ).all()
        
        total_work_minutes_this_month = sum(
            a.work_duration_minutes for a in current_month_attendances
            if a.work_duration_minutes is not None
        )

        return AttendanceStats(
            # ... field yang sudah ada ...
            total_work_minutes_this_month=total_work_minutes_this_month,  # ── TAMBAH
        )
        
        # All-time stats
        all_attendances = db.query(Attendance).filter(
            Attendance.user_id == current_user.id
        ).all()
        
        # Calculate stats
        total_attendances = len(all_attendances)
        
        if total_attendances > 0:
            wfo_percentage = (sum(1 for a in all_attendances if a.work_status == LocationType.WFO) / total_attendances) * 100
            wfh_percentage = (sum(1 for a in all_attendances if a.work_status == LocationType.WFH) / total_attendances) * 100
            
            ontime_percentage = (sum(1 for a in all_attendances if a.check_in_status == AttendanceStatus.ONTIME) / total_attendances) * 100
            late_percentage = (sum(1 for a in all_attendances if a.check_in_status == AttendanceStatus.LATE) / total_attendances) * 100
            
            first_attendance = min(all_attendances, key=lambda x: x.date) if all_attendances else None
            
            # Most frequent office
            office_counts = {}
            for a in all_attendances:
                if a.office_location_id:
                    office_counts[a.office_location_id] = office_counts.get(a.office_location_id, 0) + 1
            
            most_frequent_office_id = max(office_counts, key=office_counts.get) if office_counts else None
            most_frequent_office = None
            if most_frequent_office_id:
                office = db.query(OfficeLocation).filter(
                    OfficeLocation.id == most_frequent_office_id
                ).first()
                most_frequent_office = {
                    "name": office.name if office else "Unknown",
                    "count": office_counts[most_frequent_office_id]
                }
        else:
            wfo_percentage = 0
            wfh_percentage = 0
            ontime_percentage = 0
            late_percentage = 0
            first_attendance = None
            most_frequent_office = None
        
        # Current streak
        MAX_STREAK_DAYS = 365
        current_streak = 0
        check_date = datetime.utcnow().date()

        for _ in range(MAX_STREAK_DAYS):
            # Skip weekend
            if check_date.weekday() >= 5:
                check_date -= timedelta(days=1)
                continue
            
            attendance = db.query(Attendance).filter(
                Attendance.user_id == current_user.id,
                Attendance.date >= datetime.combine(check_date, dt_time.min),
                Attendance.date <= datetime.combine(check_date, dt_time.max)
            ).first()
            
            if attendance and attendance.check_in_time:
                current_streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        # Longest streak (simplified)
        longest_streak = current_streak  # Simplified calculation
        
        return AttendanceStats(
            total_attendances=total_attendances,
            current_month_count=len(current_month_attendances),
            wfo_percentage=round(wfo_percentage, 1),
            wfh_percentage=round(wfh_percentage, 1),
            ontime_percentage=round(ontime_percentage, 1),
            late_percentage=round(late_percentage, 1),
            current_streak=current_streak,
            longest_streak=longest_streak,
            first_attendance_date=first_attendance.date if first_attendance else None,
            most_frequent_office=most_frequent_office
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil statistik: {str(e)}"
        )

@router.get("/validate-location")
async def validate_attendance_location(
    latitude: float = Query(..., description="Latitude"),
    longitude: float = Query(..., description="Longitude"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate location without checking in
    Useful for testing if user is within valid radius
    """
    
    try:
        today = datetime.utcnow().date()
        
        # Get today's schedule
        schedule = db.query(WorkSchedule).filter(
            WorkSchedule.user_id == current_user.id,
            WorkSchedule.date >= datetime.combine(today, dt_time.min),
            WorkSchedule.date <= datetime.combine(today, dt_time.max),

        ).first()
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak ada jadwal kerja untuk hari ini"
            )
        
        if schedule.work_status != LocationType.WFO:
            return {
                "valid": True,
                "message": "WFH - Tidak perlu validasi GPS",
                "work_status": "WFH"
            }
        
        if not schedule.office_location_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lokasi kantor tidak ditentukan"
            )
        
        # Get office location
        office_location = db.query(OfficeLocation).filter(
            OfficeLocation.id == schedule.office_location_id
        ).first()
        
        if not office_location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lokasi kantor tidak ditemukan"
            )
        
        # Validate GPS
        is_valid, distance, details = GPSValidationService.is_within_radius(
            latitude, longitude,
            office_location.latitude, office_location.longitude,
            office_location.radius
        )
        
        return {
            "valid": is_valid,
            "distance_meters": round(distance, 2),
            "radius_limit": office_location.radius,
            "office_name": office_location.name,
            "work_status": "WFO",
            "details": details,
            "message": "Dalam radius kantor" if is_valid else f"Di luar radius. Jarak: {distance:.1f}m"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validasi lokasi gagal: {str(e)}"
        )

@router.get("/admin/all-attendance", dependencies=[Depends(get_current_admin)])
async def get_all_attendance_admin(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    user_id: Optional[str] = Query(None, description="User ID filter"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db)
):
    """
    Get all attendance records (Admin only)
    """
    
    try:
        query = db.query(Attendance).options(joinedload(Attendance.user))
        
        # Apply filters
        if start_date:
            query = query.filter(Attendance.date >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(Attendance.date <= datetime.combine(end_date, datetime.max.time()))
        if user_id:
            try:
                user_uuid = UUID(user_id)
                query = query.filter(Attendance.user_id == user_uuid)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid user ID format"
                )
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        attendances = query.order_by(Attendance.date.desc()).offset(offset).limit(limit).all()
        
        # ✅ Buat peta lokasi kantor untuk menghindari N+1 query
        office_ids = {att.office_location_id for att in attendances if att.office_location_id}
        office_map = {o.id: o.name for o in db.query(OfficeLocation).filter(OfficeLocation.id.in_(office_ids))} if office_ids else {}

        # Format response
        result = []
        for att in attendances:
            office_name = office_map.get(att.office_location_id)
            result.append({
                "id": att.id,
                "date": att.date,
                "user_id": att.user_id,
                "user_name": att.user.full_name if att.user else "Unknown",
                "user_email": att.user.email if att.user else "Unknown",
                "check_in_time": att.check_in_time,
                "check_out_time": att.check_out_time,
                "work_status": att.work_status,
                "office_location": office_name,
                "check_in_status": att.check_in_status,
                "check_out_status": att.check_out_status,
                "is_validated": att.is_validated
            })
        
        return {
            "items": result,
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil data attendance: {str(e)}"
        )