from haversine import haversine, Unit

OFFICE_LOCATION = (-6.200000, 106.816666)  # contoh
MAX_RADIUS_METER = 50

def validate_location(lat, lon):
    user_location = (lat, lon)
    distance = haversine(OFFICE_LOCATION, user_location, unit=Unit.METERS)
    return distance <= MAX_RADIUS_METER
