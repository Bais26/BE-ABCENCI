from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime, timedelta
import logging

from app.services.rekap import JAKARTA_TZ # Impor zona waktu
from app.core.database import get_db
from app.schemas.schedule import (
    OfficeLocationCreate, OfficeLocationResponse,
    GenerateScheduleRequest,
    TestNotificationRequest
)
from app.models.user import User, UserRole
from app.models.schedule import OfficeLocation, WorkSchedule
from app.services.genetic import generate_work_schedule # Assuming this is correct
from app.utils.security import get_current_admin, get_current_user # Corrected import path
from app.services.notification_service import send_notification

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schedule", tags=["schedule"])

@router.post("/test-notification")
async def test_notification(
    request_data: TestNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    Endpoint untuk mengetes pengiriman notifikasi ke satu user berdasarkan email.
    (Hanya untuk Admin)
    """
    target_email = request_data.email
    logger.info(f"Mencari user dengan email: {target_email} untuk tes notifikasi.")
    user = db.query(User).filter(User.email == target_email).first()

    if not user:
        logger.error(f"User dengan email {target_email} tidak ditemukan.")
        raise HTTPException(status_code=404, detail=f"User dengan email {target_email} tidak ditemukan.")

    if not user.fcm_token:
        logger.warning(f"User {target_email} tidak memiliki FCM token.")
        raise HTTPException(status_code=400, detail=f"User {target_email} tidak memiliki FCM token di database.")

    logger.info(f"User ditemukan: {user.full_name}. Mencoba mengirim notifikasi tes...")
    try:
        response = send_notification(
            token=user.fcm_token,
            title="Tes Notifikasi",
            body=f"Ini adalah pesan tes untuk {user.full_name} pada {datetime.now(JAKARTA_TZ).strftime('%Y-%m-%d %H:%M:%S')} WIB",
            data={"type": "test", "timestamp": str(datetime.now().timestamp())},
        )
        logger.info(f"Notifikasi tes berhasil dikirim ke {target_email}. Response: {response}")
        return {
            "message": "Notifikasi tes berhasil dikirim.",
            "user_email": target_email,
            "fcm_token_used": user.fcm_token,
            "firebase_response": response,
        }
    except Exception as e:
        logger.error(f"Gagal mengirim notifikasi tes ke {target_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal mengirim notifikasi: {str(e)}")


# ============ HELPER FUNCTIONS ============
def generate_simple_schedule_fallback(db: Session, start_date, end_date, min_wfo_week, max_wfo_week, office_capacity):
    """Simple schedule generator as fallback"""
    import random
    from datetime import timedelta
    
    # Get active karyawan
    karyawan_list = db.query(User).filter(
        User.role == UserRole.KARYAWAN,
        User.is_active == True
    ).all()
    
    # Get office locations
    office_locations = db.query(OfficeLocation).filter(
        OfficeLocation.is_active == True
    ).all()
    
    result = []
    
    # Generate all dates
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    
    # Calculate target WFO ratio based on min/max
    target_wfo_ratio = (min_wfo_week + max_wfo_week) / 2 / 5  # Convert to daily ratio
    
    for karyawan in karyawan_list:
        emp_schedule = {
            "employee_id": karyawan.id,
            "schedule": []
        }
        
        # Calculate target WFO days
        total_weekdays = len([d for d in dates if d.weekday() < 5])
        target_wfo_days = int(total_weekdays * target_wfo_ratio)
        
        wfo_count = 0
        
        for day_date in dates:
            # Determine work status
            if day_date.weekday() >= 5:  # Weekend
                work_status = "OFF"
            else:
                # Try to reach target WFO days
                if wfo_count < target_wfo_days and random.random() < 0.5:
                    work_status = "WFO"
                    wfo_count += 1
                else:
                    work_status = "WFH"
            
            # Assign office location for WFO
            office_location_id = None
            if work_status == "WFO" and office_locations:
                office = random.choice(office_locations)
                office_location_id = office.id
            
            emp_schedule["schedule"].append({
                "date": day_date,
                "work_status": work_status,
                "office_location_id": office_location_id
            })
        
        result.append(emp_schedule)
    
    return result

def calculate_average_wfo_per_week(schedules):
    """Calculate average WFO days per week"""
    if not schedules:
        return 0
    
    # Group by user
    user_schedules = {}
    for schedule in schedules:
        user_id = schedule.user_id
        if user_id not in user_schedules:
            user_schedules[user_id] = []
        user_schedules[user_id].append(schedule)
    
    total_wfo_ratio = 0
    for user_id, user_schedule_list in user_schedules.items():
        # Count weekdays and WFO days
        weekdays = 0
        wfo_days = 0
        
        for schedule in user_schedule_list:
            if schedule.date.weekday() < 5:  # Weekday
                weekdays += 1
                if schedule.work_status == "WFO":
                    wfo_days += 1
        
        if weekdays > 0:
            wfo_per_week = (wfo_days / weekdays) * 5
            total_wfo_ratio += wfo_per_week
    
    if user_schedules:
        return round(total_wfo_ratio / len(user_schedules), 2)
    return 0

def get_status_description(status: str) -> str:
    """Helper function untuk deskripsi status"""
    descriptions = {
        "WFO": "Work From Office",
        "WFH": "Work From Home", 
        "OFF": "Hari Libur"
    }
    return descriptions.get(status, status)

def get_user_position(user: User) -> str:
    """Helper function untuk mendapatkan jabatan user"""
    if hasattr(user, 'position') and user.position:
        return user.position
    elif hasattr(user, 'jabatan') and user.jabatan:
        return user.jabatan
    elif user.role == UserRole.KARYAWAN:
        return "Karyawan"
    else:
        return "Admin"

# ============ ENDPOINTS ============

@router.post("/locations", response_model=OfficeLocationResponse)
async def create_office_location(
    location_data: OfficeLocationCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create new office location (Admin only)"""
    
    # Check if location name exists
    existing = db.query(OfficeLocation).filter(
        OfficeLocation.name == location_data.name,
        OfficeLocation.is_active == True
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location name already exists"
        )
    
    location = OfficeLocation(
        name=location_data.name,
        address=location_data.address,
        latitude=location_data.latitude,
        longitude=location_data.longitude,
        radius=location_data.radius,
        capacity=location_data.capacity
    )
    
    db.add(location)
    db.commit()
    db.refresh(location)
    
    return location

@router.get("/locations", response_model=List[OfficeLocationResponse])
async def get_office_locations(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get all office locations"""
    
    query = db.query(OfficeLocation)
    if active_only:
        query = query.filter(OfficeLocation.is_active == True)
    
    locations = query.order_by(OfficeLocation.name).all()
    return locations

@router.get("/locations/{location_id}", response_model=OfficeLocationResponse)
async def get_office_location(
    location_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get specific office location"""
    
    location = db.query(OfficeLocation).filter(OfficeLocation.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    return location

@router.put("/locations/{location_id}", response_model=OfficeLocationResponse)
async def update_office_location(
    location_id: uuid.UUID,
    location_data: OfficeLocationCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update office location (Admin only)"""
    
    location = db.query(OfficeLocation).filter(OfficeLocation.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # Check if name already exists (excluding current location)
    if location_data.name != location.name:
        existing = db.query(OfficeLocation).filter(
            OfficeLocation.name == location_data.name,
            OfficeLocation.is_active == True,
            OfficeLocation.id != location_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Location name already exists"
            )
    
    # Update fields
    for field, value in location_data.dict().items():
        setattr(location, field, value)
    
    db.commit()
    db.refresh(location)
    
    return location

@router.delete("/locations/{location_id}")
async def delete_office_location(
    location_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Soft delete office location (Admin only)"""
    
    location = db.query(OfficeLocation).filter(OfficeLocation.id == location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    location.is_active = False
    db.commit()
    
    return {"message": "Location deleted successfully"}

@router.post("/generate")
async def generate_schedule(
    schedule_data: GenerateScheduleRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Generate work schedule menggunakan algoritma genetika (Admin only)"""
    
    logger.info("Memulai proses generate jadwal...")
    try:
        logger.info(f"Request data: Start={schedule_data.start_date}, End={schedule_data.end_date}")
        logger.info(f"Office capacity: {schedule_data.office_capacity}")
        logger.info(f"WFO/week: Min={schedule_data.min_wfo_per_week}, Max={schedule_data.max_wfo_per_week}")
        
        # Get active karyawan
        karyawan_users = db.query(User).filter(
            User.role == UserRole.KARYAWAN,
            User.is_active == True
        ).all()
        
        logger.info(f"Ditemukan {len(karyawan_users)} karyawan aktif.")
        
        if not karyawan_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak ada karyawan aktif untuk dijadwalkan"
            )
        
        try:
            # Call genetic algorithm service
            schedule_result = generate_work_schedule(db, schedule_data)
            logger.info(f"Algoritma genetika berhasil membuat jadwal untuk {len(schedule_result)} karyawan.")
            
        except Exception as e:
            logger.warning(f"Error pada algoritma genetika: {e}. Menggunakan generator fallback.")
            
            # Fallback to simple generator
            schedule_result = generate_simple_schedule_fallback(
                db, 
                schedule_data.start_date, 
                schedule_data.end_date,
                schedule_data.min_wfo_per_week,
                schedule_data.max_wfo_per_week,
                schedule_data.office_capacity
            )
            logger.info(f"Generator fallback berhasil membuat jadwal untuk {len(schedule_result)} karyawan.")
        
        # Clear existing schedules for the date range
        karyawan_ids = [user.id for user in karyawan_users]
        
        deleted_count = db.query(WorkSchedule).filter(
            WorkSchedule.date >= schedule_data.start_date,
            WorkSchedule.date <= schedule_data.end_date,
            WorkSchedule.user_id.in_(karyawan_ids)
        ).delete()
        
        logger.info(f"Menghapus {deleted_count} jadwal lama pada rentang tanggal yang sama.")
        
        # Save new schedules
        schedules_to_create = []
        work_status_counts = {"WFO": 0, "WFH": 0, "OFF": 0}
        
        for employee_schedule in schedule_result:
            for day_schedule in employee_schedule["schedule"]:
                # Ensure work_status is valid
                work_status = str(day_schedule.get("work_status", "OFF")).upper()
                
                if work_status not in ["WFO", "WFH", "OFF"]:
                    # Default based on day
                    if day_schedule["date"].weekday() >= 5:
                        work_status = "OFF"
                    else:
                        work_status = "WFH"
                
                # Count work status
                work_status_counts[work_status] = work_status_counts.get(work_status, 0) + 1
                
                schedule = WorkSchedule(
                    user_id=employee_schedule["employee_id"],
                    date=day_schedule["date"],
                    work_status=work_status,
                    office_location_id=day_schedule.get("office_location_id")
                )
                schedules_to_create.append(schedule)
        
        logger.info(f"Membuat {len(schedules_to_create)} entri jadwal baru.")
        logger.info(f"Distribusi status kerja: {work_status_counts}")
        
        # Save to database
        if schedules_to_create:
            db.bulk_save_objects(schedules_to_create)
            db.commit()
            logger.info("Jadwal baru berhasil disimpan ke database.")

            notification_results = {"success": 0, "failed": 0, "no_token": 0}
            # Kirim notifikasi ke semua karyawan
            for user in karyawan_users:
                if user.fcm_token:
                    logger.info(f"Mencoba mengirim notifikasi ke {user.full_name} ({user.email}) dengan token: {user.fcm_token[:15]}...")
                    try:
                        response = send_notification(
                            token=user.fcm_token,
                            title="Jadwal Baru",
                            body=(
                                f"Jadwal kerja telah ditetapkan "
                                f"untuk periode {schedule_data.start_date.strftime('%d %b')} - "
                                f"{schedule_data.end_date.strftime('%d %b %Y')}"
                            ),
                            data={
                                "type": "schedule",
                                "start_date": str(schedule_data.start_date),
                                "end_date": str(schedule_data.end_date),
                            },
                        )
                        logger.info(f"Notifikasi berhasil dikirim ke {user.full_name}. Response: {response}")
                        notification_results["success"] += 1
                    except Exception as e:
                        logger.error(f"GAGAL mengirim notifikasi ke {user.full_name}: {e}")
                        notification_results["failed"] += 1
                else:
                    logger.warning(f"Pengguna {user.full_name} tidak memiliki FCM token, notifikasi dilewati.")
                    notification_results["no_token"] += 1
            
            logger.info(f"Pengiriman notifikasi selesai. Hasil: {notification_results}")
        else:
            logger.warning("Tidak ada jadwal untuk disimpan.")
            
        return {
            "message": "Jadwal berhasil digenerate",
            "total_schedules": len(schedules_to_create),
            "total_karyawan": len(karyawan_users),
            "start_date": schedule_data.start_date,
            "end_date": schedule_data.end_date,
            "statistik": work_status_counts,
            "rata_rata_wfo_per_minggu": calculate_average_wfo_per_week(schedules_to_create),
            "notification_results": notification_results
        }
        
    except Exception as e:
        db.rollback()
        import traceback
        logger.error(f"Terjadi error besar di generate_schedule: {str(e)}")
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengenerate jadwal: {str(e)}"
        )
        
@router.get("/my-schedule")
async def get_my_schedule(
    start_date: datetime = None,
    end_date: datetime = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get work schedule untuk user yang login"""
    
    # Jika user adalah admin, berikan pesan khusus
    if current_user.role == UserRole.ADMIN:
        return {
            "message": "Admin tidak memiliki jadwal kerja",
            "role": "Admin",
            "schedules": []
        }
    
    # Default ke minggu ini jika tidak ada tanggal
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        # Set ke hari Senin minggu ini
        start_date = start_date - timedelta(days=start_date.weekday())
        end_date = start_date + timedelta(days=6)
    
    query = db.query(WorkSchedule).filter(
        WorkSchedule.user_id == current_user.id,
        WorkSchedule.date >= start_date,
        WorkSchedule.date <= end_date
    )
    
    schedules = query.order_by(WorkSchedule.date).all()
    
    # Hitung statistik
    total_wfo = sum(1 for s in schedules if s.work_status == "WFO")
    total_wfh = sum(1 for s in schedules if s.work_status == "WFH")
    total_off = sum(1 for s in schedules if s.work_status == "OFF")
    
    # Format response dengan hari Indonesia
    hari_indonesia = {
        0: "Senin",
        1: "Selasa", 
        2: "Rabu",
        3: "Kamis",
        4: "Jumat",
        5: "Sabtu",
        6: "Minggu"
    }
    
    # Format per tanggal
    schedules_by_date = []
    for schedule in schedules:
        office_location = None
        if schedule.office_location_id:
            office_location = db.query(OfficeLocation).filter(
                OfficeLocation.id == schedule.office_location_id
            ).first()
        
        day_name = hari_indonesia[schedule.date.weekday()]
        
        schedules_by_date.append({
            "id": schedule.id,
            "tanggal": schedule.date,
            "hari": day_name,
            "work_status": schedule.work_status,  # WFO/WFH/OFF
            "keterangan": get_status_description(schedule.work_status),
            "office_location": {
                "id": office_location.id if office_location else None,
                "name": office_location.name if office_location else None,
                "address": office_location.address if office_location else None
            } if office_location else None
        })
    
    # Format per hari untuk tampilan seperti di /all
    schedule_dict = {}
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        day_name_id = hari_indonesia[current_date.weekday()].lower()
        
        # Cari schedule untuk hari ini
        schedule_for_day = next(
            (s for s in schedules if s.date.strftime("%Y-%m-%d") == current_date.strftime("%Y-%m-%d")),
            None
        )
        
        schedule_dict[day_name_id] = schedule_for_day.work_status if schedule_for_day else "OFF"
    
    return {
        "user": {
            "id": current_user.id,
            "nama": current_user.full_name,
            "jabatan": get_user_position(current_user),
            "periode": f"{start_date.date()} hingga {end_date.date()}"
        },
        "statistik": {
            "total_hari": len(schedules),
            "WFO": total_wfo,
            "WFH": total_wfh,
            "OFF": total_off
        },
        "schedule_per_hari": schedule_dict,  # Format seperti di /all
        "detail_schedule": schedules_by_date,  # Detail per tanggal
        "periode": {
            "start_date": start_date.date(),
            "end_date": end_date.date()
        }
    }
    
@router.get("/all")
async def get_all_schedules(
    start_date: datetime = None,
    end_date: datetime = None,
    jabatan_filter: str = None,  # Filter opsional berdasarkan jabatan
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Admin: Get all user schedules dengan filter"""
    
    # Default tanggal jika tidak disediakan
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = start_date - timedelta(days=start_date.weekday())
        end_date = start_date + timedelta(days=6)
    
    # Query karyawan
    users = db.query(User).filter(
        User.is_active == True,
        User.role == UserRole.KARYAWAN
    )
    
    # Filter berdasarkan jabatan jika ada
    if jabatan_filter:
        # Asumsi ada field 'position' atau 'jabatan' di model User
        if hasattr(User, 'position'):
            users = users.filter(User.position.ilike(f"%{jabatan_filter}%"))
        elif hasattr(User, 'jabatan'):
            users = users.filter(User.jabatan.ilike(f"%{jabatan_filter}%"))
    
    users = users.order_by(User.full_name).all()
    
    result = {
        "start_date": start_date.date(),
        "end_date": end_date.date(),
        "total_karyawan": len(users),
        "jabatan_filter": jabatan_filter,
        "data": []
    }
    
    hari_indonesia = {
        0: "senin", 1: "selasa", 2: "rabu", 3: "kamis",
        4: "jumat", 5: "sabtu", 6: "minggu"
    }
    
    for index, user in enumerate(users, start=1):
        schedules = db.query(WorkSchedule).filter(
            WorkSchedule.user_id == user.id,
            WorkSchedule.date >= start_date,
            WorkSchedule.date <= end_date
        ).order_by(WorkSchedule.date).all()
        
        schedule_dict = {day: "OFF" for day in hari_indonesia.values()}
        
        for schedule in schedules:
            if schedule.work_status:
                day_name = hari_indonesia[schedule.date.weekday()]
                schedule_dict[day_name] = schedule.work_status
        
        # Tentukan jabatan untuk display
        jabatan_display = "Karyawan"
        if hasattr(user, 'position') and user.position:
            jabatan_display = user.position
        elif hasattr(user, 'jabatan') and user.jabatan:
            jabatan_display = user.jabatan
        elif hasattr(user, 'department') and user.department:
            jabatan_display = user.department
        
        result["data"].append({
            "id": f"CBN{index:03d}",
            "nama": user.full_name,
            "jabatan": jabatan_display,
            "status": "Aktif",
            "schedule": schedule_dict
        })
    
    return result

# ============ OPTIONAL: SIMPLE GENERATE ENDPOINT ============
@router.post("/generate-simple")
async def generate_simple_schedule_endpoint(
    start_date: datetime,
    end_date: datetime,
    wfo_percentage: int = 60,  # persentase hari WFO
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Generate schedule cepat dengan parameter sederhana"""
    
    try:
        # Convert percentage to ratio
        wfo_ratio = wfo_percentage / 100.0
        wfh_ratio = 1.0 - wfo_ratio  # Sisa untuk WFH
        
        # Get active karyawan
        karyawan_users = db.query(User).filter(
            User.role == UserRole.KARYAWAN,
            User.is_active == True
        ).all()
        
        # Clear existing schedules
        karyawan_ids = [user.id for user in karyawan_users]
        db.query(WorkSchedule).filter(
            WorkSchedule.date >= start_date,
            WorkSchedule.date <= end_date,
            WorkSchedule.user_id.in_(karyawan_ids)
        ).delete()
        
        # Generate schedules
        schedules_to_create = []
        import random
        from datetime import timedelta
        
        # Get office locations
        office_locations = db.query(OfficeLocation).filter(
            OfficeLocation.is_active == True
        ).all()
        
        # Generate dates
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)
        
        work_status_counts = {"WFO": 0, "WFH": 0, "OFF": 0}
        
        for user in karyawan_users:
            for day_date in dates:
                if day_date.weekday() >= 5:  # Weekend
                    work_status = "OFF"
                else:
                    if random.random() < wfo_ratio:
                        work_status = "WFO"
                    else:
                        work_status = "WFH"
                
                work_status_counts[work_status] += 1
                
                office_location_id = None
                if work_status == "WFO" and office_locations:
                    office = random.choice(office_locations)
                    office_location_id = office.id
                
                schedule = WorkSchedule(
                    user_id=user.id,
                    date=day_date,
                    work_status=work_status,
                    office_location_id=office_location_id
                )
                schedules_to_create.append(schedule)
        
        # Save to database
        if schedules_to_create:
            db.bulk_save_objects(schedules_to_create)
            db.commit()
        
        return {
            "message": "Jadwal berhasil digenerate",
            "total_schedules": len(schedules_to_create),
            "total_karyawan": len(karyawan_users),
            "start_date": start_date.date(),
            "end_date": end_date.date(),
            "wfo_percentage": wfo_percentage,
            "statistik": work_status_counts
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengenerate jadwal: {str(e)}"
        )