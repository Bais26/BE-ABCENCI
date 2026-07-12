# app/models/karyawan_detail.py
from sqlalchemy import Column, String, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.db.base import Base

class KaryawanDetail(Base):
    __tablename__ = "karyawan_details"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)

    nama_depan = Column(String)
    nama_belakang = Column(String)
    tanggal_lahir = Column(Date)
    jenis_kelamin = Column(String)
    tinggi_badan = Column(String)
    berat_badan = Column(String)
    nama_alamat = Column(String)
    alamat_lengkap = Column(String)
    detail_alamat = Column(String)
    nama_kontak_darurat = Column(String)
    hubungan_kontak_darurat = Column(String)
    nomor_telepon_darurat = Column(String)
    nama_bank = Column(String)
    nomor_rekening = Column(String)
    nama_pemilik_rekening = Column(String)
    posisi = Column(String)
    tanggal_masuk = Column(Date)
    status = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    # Foreign key ke tabel subdivisions
    subdivision_id = Column(UUID(as_uuid=True), ForeignKey("subdivisions.id"), nullable=True)
    subdivision = relationship("SubDivision", back_populates="karyawans")

    user = relationship("User", back_populates="karyawan_detail")
