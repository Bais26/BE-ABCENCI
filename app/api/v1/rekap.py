from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, time as dt_time

from app.core.database import get_db
from app.utils.security import get_current_user, get_current_admin
from app.models.user import User
from app.models.attendance import Attendance, LocationType
# from app.models import Attendance, LocationType, SubDivision, Division
from app.models.karyawan_detail import KaryawanDetail
from app.schemas.rekap import MyRekapResponse, AdminRekapResponse
from app.services.rekap import (
    get_date_range,
    count_working_days,
    get_office_map,
    build_summary,
    to_daily_item,
    query_users,
    build_karyawan_item,
    JAKARTA_TZ,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════
# GET /attendance/my-rekap
# Rekap absensi milik karyawan yang sedang login
# ══════════════════════════════════════════════════════════

@router.get("/my-rekap", response_model=MyRekapResponse)
async def get_my_rekap(
    filter: str = Query(
        "month",
        pattern="^(week|month|year)$",
        description="Periode: week | month | year",
    ),
    year: Optional[int] = Query(None, ge=2000, le=2100, description="Tahun (default: tahun ini)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Bulan 1–12 (hanya untuk filter=month)"),
    week: Optional[int] = Query(None, ge=1, le=53, description="Nomor minggu ISO (hanya untuk filter=week)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Rekap absensi milik karyawan yang sedang login.

    **Filter periode:**
    - `filter=month` (default) → rekap bulan ini atau bulan tertentu (`year` + `month`)
    - `filter=week`            → rekap mingguan (`year` + `week`)
    - `filter=year`            → rekap tahunan (`year`)

    Waktu check-in/check-out ditampilkan dalam **WIB**.
    Response berisi **summary** (ringkasan) + **detail** (daftar per hari).
    """
    try:
        now = datetime.now(JAKARTA_TZ)
        if year is None:
            year = now.year
        if filter == "month" and month is None:
            month = now.month

        start, end, label = get_date_range(filter, year, month, week)

        attendances = (
            db.query(Attendance)
            .filter(
                Attendance.user_id == current_user.id,
                Attendance.date >= datetime.combine(start, datetime.min.time()),
                Attendance.date <= datetime.combine(end, datetime.max.time()),
            )
            .order_by(Attendance.date.asc())
            .all()
        )

        office_map = get_office_map(db, attendances)
        summary = build_summary(attendances, start, end, label, filter)
        detail = [to_daily_item(a, office_map.get(a.office_location_id)) for a in attendances]

        return MyRekapResponse(summary=summary, detail=detail)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil rekap: {str(e)}",
        )


# ══════════════════════════════════════════════════════════
# GET /attendance/admin/rekap
# Rekap semua karyawan — Admin only
# ══════════════════════════════════════════════════════════

@router.get("/admin/rekap", dependencies=[Depends(get_current_admin)])
async def get_admin_rekap(
    # ── filter periode ──
    filter: str = Query(
        "month",
        pattern="^(week|month|year)$", # Menggunakan pattern sudah benar
        description="Periode: week | month | year",
    ),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    week: Optional[int] = Query(None, ge=1, le=53),
    # ── filter karyawan ──
    nama_lengkap: Optional[str] = Query(
        None, description="Cari sebagian nama karyawan (case-insensitive)"
    ),
    email: Optional[str] = Query(None, description="Cari sebagian email"),
    divisi: Optional[str] = Query(None, description="Nama divisi (case-insensitive)"),
    subdivisi: Optional[str] = Query(
        None, description="Nama subdivisi (case-insensitive)"
    ),
    posisi: Optional[str] = Query(
        None, description="Posisi / jabatan (case-insensitive)"
    ),
    user_id: Optional[str] = Query(None, description="UUID spesifik karyawan"),
    work_status: Optional[str] = Query(
        None, pattern="^(WFO|WFH)$", # Menggunakan pattern sudah benar
    ),
    # ── pagination ──
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """
    Rekap kehadiran seluruh karyawan — **Admin only**.

    **Filter karyawan:** `nama_lengkap`, `email`, `divisi`, `subdivisi`, `posisi`, `user_id`
    **Filter periode:** `filter` + `year` / `month` / `week`
    **Filter status:** `work_status` → WFO | WFH
    **Pagination:** `page` + `limit`

    Response berisi:
    - `summary`        : agregat semua karyawan yang cocok filter
    - `karyawan`       : list per-karyawan (paginated) — nama, email, posisi, divisi,
                         total WFO/WFH, ontime/terlambat/pulang awal, jam kerja, attendance rate
    - `total_karyawan` : total karyawan yang cocok filter (sebelum pagination)
    """
    try:
        now = datetime.now(JAKARTA_TZ)
        if year is None:
            year = now.year
        if filter == "month" and month is None:
            month = now.month

        start, end, label = get_date_range(filter, year, month, week)

        # ── 1. Query & filter user ──
        try:
            # Dapatkan objek query, bukan list
            users_query = query_users(db, user_id, nama_lengkap, email, divisi, subdivisi, posisi)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Format user_id tidak valid (harus UUID)"
            )

        # Hitung total dari query sebelum pagination
        total_karyawan = users_query.count()

        # ── 2. Ambil SEMUA attendance untuk SEMUA user yang cocok filter (untuk summary) ──
        all_user_ids = [u.id for u in users_query.all()] # Ambil semua ID untuk summary
        summary_att_query = db.query(Attendance).filter(
            Attendance.user_id.in_(all_user_ids),
            Attendance.date >= datetime.combine(start, datetime.min.time()),
            Attendance.date <= datetime.combine(end, datetime.max.time()),
        )
        if work_status:
            loc = LocationType.WFO if work_status == "WFO" else LocationType.WFH
            summary_att_query = summary_att_query.filter(Attendance.work_status == loc)
        
        all_attendances_for_summary = summary_att_query.all()

        # ── 3. Hitung summary berdasarkan data keseluruhan ──
        # Kalkulasi total alfa agregat untuk summary
        karyawan_cuti = users_query.join(KaryawanDetail).filter(KaryawanDetail.status == 'Cuti').count()

        total_hari_kerja_periode = count_working_days(start, end)
        # Total hari kerja yang diharapkan adalah untuk karyawan yang tidak cuti
        total_expected_workdays_all_users = total_hari_kerja_periode * (total_karyawan - karyawan_cuti)
        total_actual_attendances_all_users = len(all_attendances_for_summary)
        total_alfa_agregat = max(0, total_expected_workdays_all_users - total_actual_attendances_all_users)

        # Buat summary dengan data agregat
        summary = build_summary(all_attendances_for_summary, start, end, label, filter)
        summary.total_alfa = total_alfa_agregat # Timpa total_alfa dengan nilai agregat yang lebih akurat

        # ── 4. Pagination pada list user untuk tampilan per halaman ──
        offset = (page - 1) * limit
        paged_users = users_query.offset(offset).limit(limit).all()

        # ── 5. Kelompokkan attendance per user (dari data summary) untuk efisiensi ──
        att_by_user: dict = {u.id: [] for u in paged_users}
        for a in all_attendances_for_summary:
            if a.user_id in att_by_user:
                att_by_user[a.user_id].append(a)

        # ── 6. Bangun list rekap per karyawan untuk halaman saat ini ──
        total_hari_kerja = count_working_days(start, end)
        karyawan_list = [
            build_karyawan_item(user, att_by_user.get(user.id, []), total_hari_kerja)
            for user in paged_users
        ]

        return AdminRekapResponse(
            summary=summary,
            karyawan=karyawan_list,
            total_karyawan=total_karyawan,
            page=page,
            limit=limit,
            total_pages=(total_karyawan + limit - 1) // limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil rekap admin: {str(e)}",
        )