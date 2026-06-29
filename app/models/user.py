from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum
import uuid
from app.models.karyawan_detail import KaryawanDetail

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    KARYAWAN = "karyawan"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    fcm_token = Column(Text, nullable=True)

    role = Column(
    Enum(
        UserRole,
        name="user_role_enum",
        native_enum=True,
        create_constraint=True,
        values_callable=lambda enum: [e.value for e in enum],
    ),
    nullable=False,
    default=UserRole.KARYAWAN.value,  
    server_default="karyawan"
)


    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    phone_number = Column(String)
    address = Column(Text)
    date_of_birth = Column(Date)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    karyawan_detail = relationship(
        "KaryawanDetail",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    attendances = relationship("Attendance", back_populates="user")
    schedules = relationship("WorkSchedule", back_populates="user")
