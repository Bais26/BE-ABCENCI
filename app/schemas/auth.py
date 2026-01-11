# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum
from uuid import UUID

class UserRole(str, Enum):
    ADMIN = "admin"
    KARYAWAN = "karyawan"

class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=3)
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str
    role: UserRole = Field(default=UserRole.KARYAWAN)
    
    # Optional fields
    phone_number: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    
    @field_validator('confirm_password')
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

class UserResponse(BaseModel):
    id: UUID  # ✅ UUID instead of int
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    phone_number: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8)
    confirm_password: str
    
    @field_validator('confirm_password')
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v

# Schema untuk Karyawan Detail
class KaryawanDetailBase(BaseModel):
    nama_depan: Optional[str] = None
    nama_belakang: Optional[str] = None
    tanggal_lahir: Optional[date] = None
    jenis_kelamin: Optional[str] = None
    tinggi_badan: Optional[str] = None
    berat_badan: Optional[str] = None
    nama_alamat: Optional[str] = None
    alamat_lengkap: Optional[str] = None
    detail_alamat: Optional[str] = None
    nama_kontak_darurat: Optional[str] = None
    hubungan_kontak_darurat: Optional[str] = None
    nomor_telepon_darurat: Optional[str] = None
    nama_bank: Optional[str] = None
    nomor_rekening: Optional[str] = None
    nama_pemilik_rekening: Optional[str] = None
    posisi: Optional[str] = None
    tanggal_masuk: Optional[date] = None
    status: Optional[str] = None

class KaryawanDetailCreate(KaryawanDetailBase):
    pass

class KaryawanDetailUpdate(KaryawanDetailBase):
    pass

class KaryawanDetailResponse(KaryawanDetailBase):
    id: UUID  # ✅ UUID instead of int
    user_id: UUID  # ✅ UUID instead of int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserWithDetailResponse(UserResponse):
    karyawan_detail: Optional[KaryawanDetailResponse] = None
    
    class Config:
        from_attributes = True
        
class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool

# ✅ NEW: Paginated Response Schema
class PaginatedKaryawanResponse(BaseModel):
    data: List[UserWithDetailResponse]  # ✅ Specify exact type
    pagination: PaginationMeta