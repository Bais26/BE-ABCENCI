from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.services.gps import GPSValidationService
from app.utils.security import get_current_user, get_current_admin
from app.models.user import User

router = APIRouter(prefix="/gps", tags=["gps"])

class GPSValidationRequest(BaseModel):
    user_latitude: float = Field(..., ge=-90, le=90)
    user_longitude: float = Field(..., ge=-180, le=180)
    office_latitude: float = Field(..., ge=-90, le=90)
    office_longitude: float = Field(..., ge=-180, le=180)
    radius_meters: float = Field(..., gt=0)
    use_geopy: bool = Field(default=False)

class GPSValidationResponse(BaseModel):
    is_valid: bool
    distance_meters: float
    is_within_radius: bool
    details: dict
    timestamp: datetime

class MultiLocationValidationRequest(BaseModel):
    user_latitude: float = Field(..., ge=-90, le=90)
    user_longitude: float = Field(..., ge=-180, le=180)
    offices: List[dict]

class LocationAnalysisRequest(BaseModel):
    user_latitude: float = Field(..., ge=-90, le=90)
    user_longitude: float = Field(..., ge=-180, le=180)
    office_latitude: float = Field(..., ge=-90, le=90)
    office_longitude: float = Field(..., ge=-180, le=180)
    radius_meters: float = Field(..., gt=0)

@router.post("/validate", response_model=GPSValidationResponse)
async def validate_gps_location(
    request: GPSValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate GPS location against office location"""
    
    try:
        is_within, distance, details = GPSValidationService.is_within_radius(
            request.user_latitude,
            request.user_longitude,
            request.office_latitude,
            request.office_longitude,
            request.radius_meters,
            request.use_geopy
        )
        
        return GPSValidationResponse(
            is_valid=True,
            distance_meters=distance,
            is_within_radius=is_within,
            details=details,
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GPS validation failed: {str(e)}"
        )

@router.post("/analyze")
async def analyze_location(
    request: LocationAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """Get detailed analysis of location relative to office"""
    
    try:
        analysis = GPSValidationService.get_location_analysis(
            request.user_latitude,
            request.user_longitude,
            request.office_latitude,
            request.office_longitude,
            request.radius_meters
        )
        
        return analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Location analysis failed: {str(e)}"
        )

@router.post("/validate-multiple")
async def validate_multiple_locations(
    request: MultiLocationValidationRequest,
    current_user: User = Depends(get_current_user)
):
    """Validate against multiple office locations"""
    
    try:
        results = GPSValidationService.check_multiple_locations(
            request.user_latitude,
            request.user_longitude,
            request.offices
        )
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Multiple location validation failed: {str(e)}"
        )

@router.get("/distance")
async def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    method: str = "haversine",  # or "geopy"
    current_user: User = Depends(get_current_user)
):
    """Calculate distance between two coordinates"""
    
    try:
        if method.lower() == "geopy":
            distance = GPSValidationService.calculate_distance_geopy(lat1, lon1, lat2, lon2)
        else:
            distance = GPSValidationService.calculate_distance_haversine(lat1, lon1, lat2, lon2)
        
        return {
            "point1": {"latitude": lat1, "longitude": lon1},
            "point2": {"latitude": lat2, "longitude": lon2},
            "distance_meters": distance,
            "distance_kilometers": distance / 1000,
            "calculation_method": method,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Distance calculation failed: {str(e)}"
        )

@router.get("/test-coordinates")
async def test_gps_coordinates(
    current_user: User = Depends(get_current_admin)
):
    """Get example coordinates for testing (Admin only)"""
    
    # Contoh koordinat kantor di Bandung
    example_offices = [
        {
            "name": "Kantor Pusat Antapani",
            "latitude": -6.917464,
            "longitude": 107.619125,
            "radius": 50,
            "address": "Jl. Sukonoagora No.31, Antapani"
        },
        {
            "name": "Kantor Cabang Dago",
            "latitude": -6.873678,
            "longitude": 107.608849,
            "radius": 100,
            "address": "Jl. Dago No.123, Bandung"
        }
    ]
    
    # Contoh koordinat user di sekitar kantor
    user_locations = [
        {
            "name": "Dalam radius kantor",
            "latitude": -6.917400,
            "longitude": 107.619100,
            "expected_within_radius": True
        },
        {
            "name": "Di luar radius kantor",
            "latitude": -6.920000,
            "longitude": 107.620000,
            "expected_within_radius": False
        }
    ]
    
    return {
        "example_offices": example_offices,
        "user_test_locations": user_locations,
        "note": "Gunakan koordinat ini untuk testing GPS validation"
    }