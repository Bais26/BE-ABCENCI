# app/routers/karyawan.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.models import User, KaryawanDetail, UserRole
from app.schemas.auth import UserWithDetailResponse, UserResponse, KaryawanDetailResponse, KaryawanDetailCreate, KaryawanDetailUpdate, PaginatedKaryawanResponse, PaginationMeta
# from app.dependencies import get_current_user, get_current_admin_user  # Untuk authentication

router = APIRouter(tags=["Karyawan"])


# =====================================
# GET ALL KARYAWAN (LIST)
# =====================================
@router.get("/", response_model=PaginatedKaryawanResponse)
def get_all_karyawan(
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_admin_user),  # ✅ Uncomment untuk protect dengan auth
    
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    
    # Filtering
    search: Optional[str] = Query(None, description="Search by name or email"),
    status: Optional[str] = Query(None, description="Filter by status (Aktif, Cuti, dll)"),
    posisi: Optional[str] = Query(None, description="Filter by position"),
    
    # Sorting
    sort_by: str = Query("created_at", description="Sort by field (created_at, full_name, email)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)")
):
    """
    Get all karyawan with pagination, filtering, and sorting
    
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 10, max: 100)
    - **search**: Search by name or email
    - **status**: Filter by karyawan status
    - **posisi**: Filter by position
    - **sort_by**: Field to sort by
    - **sort_order**: asc or desc
    """
    
    # Base query - hanya ambil user dengan role KARYAWAN
    query = db.query(User).options(
        joinedload(User.karyawan_detail).joinedload(KaryawanDetail.division)
    ).filter(User.role == UserRole.KARYAWAN.value)
    
    # ✅ FILTERING
    needs_detail_join = False
    if search:
        search_filter = or_(
            User.full_name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    if status:
        needs_detail_join = True
        query = query.filter(KaryawanDetail.status == status)
    if posisi:
        needs_detail_join = True
        query = query.filter(KaryawanDetail.posisi.ilike(f"%{posisi}%"))
    if needs_detail_join:
        query = query.join(KaryawanDetail, User.id == KaryawanDetail.user_id, isouter=True)
    
    # ✅ SORTING
    sort_field_map = {
        "full_name": User.full_name,
        "email": User.email,
        "created_at": User.created_at,
        "posisi": KaryawanDetail.posisi,
        "status": KaryawanDetail.status,
    }

    # Jika sorting butuh join ke KaryawanDetail, pastikan join ada
    if sort_by in ["posisi", "status"] and not needs_detail_join:
        query = query.join(KaryawanDetail, User.id == KaryawanDetail.user_id, isouter=True)

    sort_column = sort_field_map.get(sort_by, User.created_at)

    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # ✅ COUNT TOTAL (before pagination)
    total = query.count()
    
    # ✅ PAGINATION
    skip = (page - 1) * limit
    karyawan_list = query.offset(skip).limit(limit).all()
    
    # ✅ CALCULATE PAGINATION INFO
    total_pages = (total + limit - 1) // limit  # Ceiling division
    
    return PaginatedKaryawanResponse(
        pagination=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        ),
        data=karyawan_list
    )


# =====================================
# GET KARYAWAN BY ID (DETAIL)
# =====================================
@router.get("/{karyawan_id}", response_model=UserWithDetailResponse)
def get_karyawan_by_id(
    karyawan_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Ambil data karyawan (admin) + karyawan_detail (jika ada)
    Tidak melempar 404 jika karyawan_detail kosong
    """

    karyawan = (
        db.query(User)
        .options(joinedload(User.karyawan_detail))
        .filter(
            User.id == karyawan_id,
            User.role == UserRole.KARYAWAN.value
        )
        .first()
    )

    if not karyawan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Karyawan not found"
        )

    detail = karyawan.karyawan_detail
    karyawan_detail_response = None
    
    division: Optional[DivisionResponse] = None

    if detail:
        from app.schemas.auth import KaryawanDetailResponse
        karyawan_detail_response = KaryawanDetailResponse(
            id=detail.id,
            user_id=detail.user_id,
            nama_depan=detail.nama_depan,
            nama_belakang=detail.nama_belakang,
            division={
                "id": detail.division.id,
                "name": detail.division.name
            } if detail.division else None,
            tanggal_lahir=detail.tanggal_lahir,
            jenis_kelamin=detail.jenis_kelamin,
            tinggi_badan=detail.tinggi_badan,
            berat_badan=detail.berat_badan,
            nama_alamat=detail.nama_alamat,
            alamat_lengkap=detail.alamat_lengkap,
            detail_alamat=detail.detail_alamat,
            nama_kontak_darurat=detail.nama_kontak_darurat,
            hubungan_kontak_darurat=detail.hubungan_kontak_darurat,
            nomor_telepon_darurat=detail.nomor_telepon_darurat,
            nama_bank=detail.nama_bank,
            nomor_rekening=detail.nomor_rekening,
            nama_pemilik_rekening=detail.nama_pemilik_rekening,
            posisi=detail.posisi,
            tanggal_masuk=detail.tanggal_masuk,
            status=detail.status,
            created_at=detail.created_at,
            updated_at=detail.updated_at
        )

    return UserWithDetailResponse(
        id=karyawan.id,
        full_name=karyawan.full_name,
        email=karyawan.email,
        role=karyawan.role,
        is_active=karyawan.is_active,
        phone_number=karyawan.phone_number,
        address=karyawan.address,
        date_of_birth=karyawan.date_of_birth,
        created_at=karyawan.created_at,
        karyawan_detail=karyawan_detail_response
    )


# =====================================
# CREATE KARYAWAN DETAIL
# =====================================
@router.post("/{karyawan_id}/detail", response_model=KaryawanDetailResponse)
def create_karyawan_detail(
    karyawan_id: UUID,
    detail: KaryawanDetailCreate,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_admin_user),  # ✅ Only admin can create
):
    """
    Create detail for karyawan
    """
    # Cek apakah karyawan exists
    karyawan = db.query(User).filter(
        User.id == karyawan_id,
        User.role == UserRole.KARYAWAN.value
    ).first()
    
    if not karyawan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Karyawan not found"
        )
    
    # Cek apakah detail sudah ada
    existing_detail = db.query(KaryawanDetail).filter(
        KaryawanDetail.user_id == karyawan_id
    ).first()
    
    if existing_detail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Karyawan detail already exists. Use PUT to update."
        )
    
    # Create detail
    new_detail = KaryawanDetail(
        user_id=karyawan_id,
        **detail.model_dump()
    )
    
    db.add(new_detail)
    db.commit()
    db.refresh(new_detail)
    
    return new_detail


# =====================================
# UPDATE KARYAWAN DETAIL
# =====================================
@router.put("/{karyawan_id}/detail", response_model=KaryawanDetailResponse)
def update_karyawan_detail(
    karyawan_id: UUID,
    detail: KaryawanDetailUpdate,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_admin_user),  # ✅ Only admin can update
):
    """
    Update karyawan detail
    """
    # Cek apakah detail exists
    existing_detail = db.query(KaryawanDetail).filter(
        KaryawanDetail.user_id == karyawan_id
    ).first()
    
    if not existing_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Karyawan detail not found. Use POST to create."
        )
    
    # Update hanya field yang di-provide (tidak None)
    update_data = detail.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(existing_detail, field, value)
    
    db.commit()
    db.refresh(existing_detail)
    
    return existing_detail


# =====================================
# DELETE KARYAWAN DETAIL
# =====================================
@router.delete("/{karyawan_id}/detail", status_code=status.HTTP_204_NO_CONTENT)
def delete_karyawan_detail(
    karyawan_id: UUID,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_admin_user),  # ✅ Only admin can delete
):
    """
    Delete karyawan detail
    """
    detail = db.query(KaryawanDetail).filter(
        KaryawanDetail.user_id == karyawan_id
    ).first()
    
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Karyawan detail not found"
        )
    
    db.delete(detail)
    db.commit()
    
    return None


# =====================================
# GET KARYAWAN STATISTICS
# =====================================
@router.get("/stats/summary", response_model=dict)
def get_karyawan_stats(
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_admin_user),
):
    """
    Get karyawan statistics summary
    """
    from sqlalchemy import func, case
    
    # Total karyawan
    total_karyawan = db.query(func.count(User.id)).filter(
        User.role == UserRole.KARYAWAN.value
    ).scalar()
    
    # Karyawan aktif
    active_karyawan = db.query(func.count(User.id)).filter(
        User.role == UserRole.KARYAWAN.value,
        User.is_active == True
    ).scalar()
    
    # Group by status
    status_counts = db.query(
        KaryawanDetail.status,
        func.count(KaryawanDetail.id)
    ).group_by(KaryawanDetail.status).all()
    
    # Group by posisi
    posisi_counts = db.query(
        KaryawanDetail.posisi,
        func.count(KaryawanDetail.id)
    ).group_by(KaryawanDetail.posisi).all()
    
    return {
        "total_karyawan": total_karyawan,
        "active_karyawan": active_karyawan,
        "inactive_karyawan": total_karyawan - active_karyawan,
        "by_status": {status: count for status, count in status_counts if status},
        "by_posisi": {posisi: count for posisi, count in posisi_counts if posisi}
    }