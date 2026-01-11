# app/models/user.py
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum
import uuid

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    KARYAWAN = "karyawan"

class User(Base):
    __tablename__ = "users"

    # ✅ UUID sebagai primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.KARYAWAN, server_default='KARYAWAN')
    is_active = Column(Boolean, default=True, server_default='true')
    
    # Kolom tambahan
    phone_number = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    karyawan_detail = relationship("KaryawanDetail", back_populates="user", uselist=False, cascade="all, delete-orphan")

class KaryawanDetail(Base):
    __tablename__ = "karyawan_details"

    # ✅ UUID sebagai primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Data Diri
    nama_depan = Column(String, nullable=True)
    nama_belakang = Column(String, nullable=True)
    tanggal_lahir = Column(Date, nullable=True)
    jenis_kelamin = Column(String, nullable=True)  # Laki-laki/Perempuan
    tinggi_badan = Column(String, nullable=True)  # contoh: "179cm"
    berat_badan = Column(String, nullable=True)   # contoh: "82kg"
    
    # Alamat
    nama_alamat = Column(String, nullable=True)  # contoh: "Apartemen"
    alamat_lengkap = Column(Text, nullable=True)
    detail_alamat = Column(String, nullable=True)
    
    # Kontak Darurat
    nama_kontak_darurat = Column(String, nullable=True)
    hubungan_kontak_darurat = Column(String, nullable=True)
    nomor_telepon_darurat = Column(String, nullable=True)
    
    # Data Rekening Bank
    nama_bank = Column(String, nullable=True)
    nomor_rekening = Column(String, nullable=True)
    nama_pemilik_rekening = Column(String, nullable=True)
    
    # Info Pekerjaan
    posisi = Column(String, nullable=True)
    tanggal_masuk = Column(Date, nullable=True)
    status = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    user = relationship("User", back_populates="karyawan_detail")