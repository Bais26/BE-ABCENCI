"""
Mock GPS service untuk testing tanpa dependency eksternal.
Digunakan saat geopy tidak diinstall atau untuk testing.
"""

class MockGPSService:
    """Mock service untuk testing GPS validation"""
    
    @staticmethod
    def validate_gps_location(
        user_lat: float, 
        user_lng: float, 
        office_lat: float, 
        office_lng: float, 
        radius: float
    ) -> bool:
        """
        Mock validation - always returns True for testing.
        In production, use the real GPSValidationService.
        """
        # For testing purposes, you can add logic here
        # For example, always return True if coordinates are provided
        if user_lat is not None and user_lng is not None:
            return True
        return False
    
    @staticmethod
    def get_mock_location_analysis(
        user_lat: float, 
        user_lng: float, 
        office_lat: float, 
        office_lng: float, 
        radius: float
    ) -> dict:
        """Return mock analysis for testing"""
        return {
            "is_within_radius": True,
            "distance_meters": 25.5,
            "radius_limit": radius,
            "validation_result": "VALID",
            "direction": "NE",
            "walking_time_minutes": 3.2,
            "note": "Mock data for testing"
        }