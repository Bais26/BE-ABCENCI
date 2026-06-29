import math
from typing import Tuple, Optional, Dict, Any
from datetime import datetime
from geopy.distance import geodesic  # Alternative library for more accurate calculations

class GPSValidationService:
    """Service untuk validasi GPS lokasi absensi"""
    
    # Earth's radius in meters
    EARTH_RADIUS = 6371000
    
    @staticmethod
    def calculate_distance_haversine(
        lat1: float, 
        lon1: float, 
        lat2: float, 
        lon2: float
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Args:
            lat1: Latitude of first point in degrees
            lon1: Longitude of first point in degrees
            lat2: Latitude of second point in degrees
            lon2: Longitude of second point in degrees
            
        Returns:
            Distance in meters
        """
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        # Haversine formula
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = GPSValidationService.EARTH_RADIUS * c
        return distance
    
    @staticmethod
    def calculate_distance_geopy(
        lat1: float, 
        lon1: float, 
        lat2: float, 
        lon2: float
    ) -> float:
        """
        Calculate distance using geopy library (more accurate).
        Requires: pip install geopy
        
        Args:
            lat1: Latitude of first point in degrees
            lon1: Longitude of first point in degrees
            lat2: Latitude of second point in degrees
            lon2: Longitude of second point in degrees
            
        Returns:
            Distance in meters
        """
        try:
            from geopy.distance import geodesic
            point1 = (lat1, lon1)
            point2 = (lat2, lon2)
            return geodesic(point1, point2).meters
        except ImportError:
            # Fallback to Haversine if geopy not installed
            return GPSValidationService.calculate_distance_haversine(lat1, lon1, lat2, lon2)
    
    @staticmethod
    def is_within_radius(
        user_lat: float, 
        user_lng: float, 
        office_lat: float, 
        office_lng: float, 
        radius: float,
        use_geopy: bool = False
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Check if user is within allowed radius of office location.
        
        Args:
            user_lat: User's latitude
            user_lng: User's longitude
            office_lat: Office latitude
            office_lng: Office longitude
            radius: Allowed radius in meters
            use_geopy: Whether to use geopy for calculation (more accurate)
            
        Returns:
            Tuple of (is_within_radius, distance_meters, details)
        """
        # Validate coordinates
        if not GPSValidationService._validate_coordinates(user_lat, user_lng):
            return False, 0, {"error": "Invalid user coordinates"}
        
        if not GPSValidationService._validate_coordinates(office_lat, office_lng):
            return False, 0, {"error": "Invalid office coordinates"}
        
        # Calculate distance
        if use_geopy:
            distance = GPSValidationService.calculate_distance_geopy(
                user_lat, user_lng, office_lat, office_lng
            )
        else:
            distance = GPSValidationService.calculate_distance_haversine(
                user_lat, user_lng, office_lat, office_lng
            )
        
        # Check if within radius
        is_within = distance <= radius
        
        # Prepare details
        details = {
            "distance_meters": round(distance, 2),
            "radius_limit": radius,
            "distance_difference": round(radius - distance, 2) if is_within else round(distance - radius, 2),
            "user_coordinates": {"lat": user_lat, "lng": user_lng},
            "office_coordinates": {"lat": office_lat, "lng": office_lng},
            "calculation_method": "geopy" if use_geopy else "haversine",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return is_within, distance, details
    
    @staticmethod
    def validate_gps_location(
        user_lat: float, 
        user_lng: float, 
        office_lat: float, 
        office_lng: float, 
        radius: float,
        use_geopy: bool = False
    ) -> bool:
        """
        Simplified validation function for FastAPI endpoints.
        
        Args:
            user_lat: User's latitude
            user_lng: User's longitude
            office_lat: Office latitude
            office_lng: Office longitude
            radius: Allowed radius in meters
            use_geopy: Whether to use geopy for calculation
            
        Returns:
            Boolean indicating if user is within radius
        """
        is_within, _, _ = GPSValidationService.is_within_radius(
            user_lat, user_lng, office_lat, office_lng, radius, use_geopy
        )
        return is_within
    
    @staticmethod
    def calculate_bearing(
        lat1: float, 
        lon1: float, 
        lat2: float, 
        lon2: float
    ) -> float:
        """
        Calculate initial bearing from point 1 to point 2.
        
        Args:
            lat1: Starting latitude
            lon1: Starting longitude
            lat2: Target latitude
            lon2: Target longitude
            
        Returns:
            Bearing in degrees (0-360)
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)
        
        x = math.sin(delta_lon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
        
        bearing = math.atan2(x, y)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360
        
        return bearing
    
    @staticmethod
    def get_direction_from_bearing(bearing: float) -> str:
        """
        Get compass direction from bearing.
        
        Args:
            bearing: Bearing in degrees
            
        Returns:
            Compass direction (N, NE, E, SE, S, SW, W, NW)
        """
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(bearing / 45) % 8
        return directions[index]
    
    @staticmethod
    def get_location_analysis(
        user_lat: float, 
        user_lng: float, 
        office_lat: float, 
        office_lng: float, 
        radius: float
    ) -> Dict[str, Any]:
        """
        Get detailed analysis of user's location relative to office.
        
        Args:
            user_lat: User's latitude
            user_lng: User's longitude
            office_lat: Office latitude
            office_lng: Office longitude
            radius: Allowed radius
            
        Returns:
            Dictionary with detailed analysis
        """
        is_within, distance, base_details = GPSValidationService.is_within_radius(
            user_lat, user_lng, office_lat, office_lng, radius, use_geopy=True
        )
        
        # Calculate bearing and direction
        bearing = GPSValidationService.calculate_bearing(
            office_lat, office_lng, user_lat, user_lng
        )
        direction = GPSValidationService.get_direction_from_bearing(bearing)
        
        # Calculate approximate walking time (assuming 5 km/h walking speed)
        walking_speed_kmh = 5
        walking_speed_ms = walking_speed_kmh * 1000 / 3600  # Convert to m/s
        walking_time_seconds = distance / walking_speed_ms if distance > 0 else 0
        walking_time_minutes = walking_time_seconds / 60
        
        # Prepare detailed analysis
        analysis = {
            **base_details,
            "is_within_radius": is_within,
            "validation_result": "VALID" if is_within else "INVALID",
            "bearing_degrees": round(bearing, 2),
            "direction": direction,
            "walking_time_minutes": round(walking_time_minutes, 1),
            "walking_time_formatted": f"{int(walking_time_minutes)} menit {int((walking_time_minutes % 1) * 60)} detik",
            "radius_coverage_percentage": min(100, round((distance / radius) * 100, 2)) if radius > 0 else 0,
            "distance_category": GPSValidationService._get_distance_category(distance),
            "recommendation": "Langsung check-in" if is_within else "Mendekat ke lokasi kantor"
        }
        
        return analysis
    
    @staticmethod
    def _validate_coordinates(lat: float, lng: float) -> bool:
        """
        Validate latitude and longitude coordinates.
        
        Args:
            lat: Latitude (-90 to 90)
            lng: Longitude (-180 to 180)
            
        Returns:
            Boolean indicating if coordinates are valid
        """
        if lat is None or lng is None:
            return False
        
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            return False
        
        if not (-90 <= lat <= 90):
            return False
        
        if not (-180 <= lng <= 180):
            return False
        
        return True
    
    @staticmethod
    def _get_distance_category(distance_meters: float) -> str:
        """
        Categorize distance for reporting.
        
        Args:
            distance_meters: Distance in meters
            
        Returns:
            Distance category
        """
        if distance_meters < 10:
            return "Sangat Dekat"
        elif distance_meters < 50:
            return "Dekat"
        elif distance_meters < 100:
            return "Sedang"
        elif distance_meters < 200:
            return "Agak Jauh"
        elif distance_meters < 500:
            return "Jauh"
        else:
            return "Sangat Jauh"
    
    @staticmethod
    def check_multiple_locations(
        user_lat: float,
        user_lng: float,
        office_locations: list,
        use_geopy: bool = False
    ) -> Dict[str, Any]:
        """
        Check user against multiple office locations.
        
        Args:
            user_lat: User's latitude
            user_lng: User's longitude
            office_locations: List of office location dicts with lat, lng, radius, name
            use_geopy: Whether to use geopy for calculation
            
        Returns:
            Dictionary with results for all locations
        """
        if not GPSValidationService._validate_coordinates(user_lat, user_lng):
            return {
                "is_valid_user_location": False,
                "error": "Invalid user coordinates",
                "nearest_location": None,
                "all_results": []
            }
        
        results = []
        nearest_distance = float('inf')
        nearest_location = None
        
        for office in office_locations:
            is_within, distance, details = GPSValidationService.is_within_radius(
                user_lat, user_lng,
                office['latitude'], office['longitude'],
                office['radius'],
                use_geopy
            )
            
            result = {
                "office_name": office.get('name', 'Unknown'),
                "office_id": office.get('id'),
                "is_within_radius": is_within,
                "distance_meters": round(distance, 2),
                "radius_limit": office['radius'],
                "details": details
            }
            
            results.append(result)
            
            # Track nearest location
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_location = {
                    "office_name": office.get('name', 'Unknown'),
                    "office_id": office.get('id'),
                    "distance_meters": round(distance, 2)
                }
        
        # Sort by distance
        results.sort(key=lambda x: x['distance_meters'])
        
        return {
            "is_valid_user_location": True,
            "nearest_location": nearest_location,
            "all_results": results,
            "total_offices_checked": len(results),
            "within_radius_count": sum(1 for r in results if r['is_within_radius']),
            "timestamp": datetime.utcnow().isoformat()
        }

# Alias functions for backward compatibility
def validate_gps_location(
    user_lat: float, 
    user_lng: float, 
    office_lat: float, 
    office_lng: float, 
    radius: float
) -> bool:
    """Simple validation function for backward compatibility"""
    return GPSValidationService.validate_gps_location(
        user_lat, user_lng, office_lat, office_lng, radius
    )

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance for backward compatibility"""
    return GPSValidationService.calculate_distance_haversine(lat1, lon1, lat2, lon2)