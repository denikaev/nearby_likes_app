import math, os, geohash2
from datetime import datetime, timedelta

NEARBY_METERS = int(os.getenv("NEARBY_METERS", "50"))
LIKE_COOLDOWN_SECONDS = int(os.getenv("LIKE_COOLDOWN_SECONDS", "300"))
GEOHASH_COOLDOWN_SECONDS = int(os.getenv("GEOHASH_COOLDOWN_SECONDS", "900"))

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def encode_geohash(lat, lon, precision=7):
    return geohash2.encode(lat, lon, precision=precision)

def now_utc():
    from datetime import timezone
    return datetime.now(tz=timezone.utc)

def like_cooldown_deadline():
    return now_utc() - timedelta(seconds=LIKE_COOLDOWN_SECONDS)

def geohash_cooldown_deadline():
    return now_utc() - timedelta(seconds=GEOHASH_COOLDOWN_SECONDS)
