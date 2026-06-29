# app/schemas/schedule.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import date
from typing import Optional, List
import uuid
from pydantic import EmailStr
class OfficeLocationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    address: str = Field(..., min_length=5)
    latitude: float
    longitude: float
    radius: int = Field(..., ge=50, le=300)  # 50-300 meters
    capacity: int = Field(..., gt=0)
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

class TestNotificationRequest(BaseModel):
    email: EmailStr = Field(..., description="Email pengguna yang akan menerima notifikasi tes.")

class OfficeLocationResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    latitude: float
    longitude: float
    radius: int
    capacity: int
    is_active: bool
    
    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )

class GenerateScheduleRequest(BaseModel):
    start_date: date
    end_date: date
    office_capacity: int = Field(..., gt=0)
    min_wfo_per_week: int = Field(..., ge=0, le=5)
    max_wfo_per_week: int = Field(..., ge=1, le=5)
    population_size: int = Field(100, ge=10, le=1000)
    generations: int = Field(100, ge=10, le=1000)
    mutation_rate: float = Field(0.01, ge=0.001, le=0.1)
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )