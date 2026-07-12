from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid


class Division(Base):
    __tablename__ = "divisions"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    description = Column(String)
 
    # Relasi ke SubDivision
    subdivisions = relationship("SubDivision", back_populates="division", cascade="all, delete-orphan")
 
 
class SubDivision(Base):
    __tablename__ = "subdivisions"
 
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    division_id = Column(UUID(as_uuid=True), ForeignKey("divisions.id"), nullable=False)

    # Relasi ke Division dan KaryawanDetail
    division = relationship("Division", back_populates="subdivisions")
    karyawans = relationship("KaryawanDetail", back_populates="subdivision", cascade="all, delete-orphan")