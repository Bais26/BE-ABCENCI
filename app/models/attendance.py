from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
import uuid
from app.db.base import Base

class AttendanceStatus(str, enum.Enum):
    ONTIME = "ontime"
    LATE = "late"
    EARLY = "early"
    ABSENT = "absent"

class LocationType(str, enum.Enum):
    WFO = "wfo"
    WFH = "wfh"

class Attendance(Base):
    __tablename__ = "attendances"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    date = Column(DateTime, default=datetime.utcnow)
    
    # Check-in data
    check_in_time = Column(DateTime)
    check_in_lat = Column(Float)
    check_in_lng = Column(Float)
    check_in_status = Column(
        Enum(AttendanceStatus),
        default=AttendanceStatus.ABSENT,
        nullable=False
    )
    check_in_location_type = Column(Enum(LocationType))
    
    # Check-out data
    check_out_time = Column(DateTime)
    check_out_lat = Column(Float)
    check_out_lng = Column(Float)
    check_out_status = Column(Enum(AttendanceStatus))
    work_duration_minutes = Column(Integer, nullable=True)
    
    # Work status
    work_status = Column(Enum(LocationType), nullable=False)
    office_location_id = Column(UUID(as_uuid=True), ForeignKey("office_locations.id"), nullable=True)
    
    # Validation
    is_validated = Column(Boolean, default=False)
    validation_note = Column(String(500))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="attendances")
    office_location = relationship("OfficeLocation", back_populates="attendances")