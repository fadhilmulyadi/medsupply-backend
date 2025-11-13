import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Menghitung jarak great-circle (jarak terpendek pada permukaan bumi) antara dua titik
    yang dinyatakan dalam koordinat derajat desimal.
    Mengembalikan nilai jarak dalam satuan kilometer.
    """
    rlat1 = math.radians(lat1)
    rlon1 = math.radians(lon1)
    rlat2 = math.radians(lat2)
    rlon2 = math.radians(lon2)

    dlon = rlon2 - rlon1
    dlat = rlat2 - rlat1

    a = math.sin(dlat / 2.0) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2.0) ** 2
    c = 2 * math.asin(math.sqrt(a))

    radius_earth_km = 6371.0
    distance_km = radius_earth_km * c
    return distance_km
