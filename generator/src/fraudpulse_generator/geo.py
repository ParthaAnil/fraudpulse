"""Indian cities with their map positions, and the distance between two places."""

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class City:
    name: str
    latitude: float
    longitude: float
    weight: int  # how common this city is: bigger cities get more users and payments


CITIES: tuple[City, ...] = (
    City("Mumbai", 19.0760, 72.8777, 20),
    City("Delhi", 28.6139, 77.2090, 20),
    City("Bengaluru", 12.9716, 77.5946, 16),
    City("Hyderabad", 17.3850, 78.4867, 12),
    City("Chennai", 13.0827, 80.2707, 11),
    City("Kolkata", 22.5726, 88.3639, 11),
    City("Pune", 18.5204, 73.8567, 9),
    City("Ahmedabad", 23.0225, 72.5714, 8),
    City("Jaipur", 26.9124, 75.7873, 5),
    City("Lucknow", 26.8467, 80.9462, 5),
    City("Kochi", 9.9312, 76.2673, 4),
    City("Chandigarh", 30.7333, 76.7794, 3),
    City("Bhopal", 23.2599, 77.4126, 3),
    City("Indore", 22.7196, 75.8577, 3),
    City("Guwahati", 26.1445, 91.7362, 2),
)

CITY_BY_NAME: dict[str, City] = {city.name: city for city in CITIES}


def distance_km(a: City, b: City) -> float:
    """Distance between two cities over the Earth's surface (the haversine formula)."""
    lat1, lon1 = math.radians(a.latitude), math.radians(a.longitude)
    lat2, lon2 = math.radians(b.latitude), math.radians(b.longitude)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))
