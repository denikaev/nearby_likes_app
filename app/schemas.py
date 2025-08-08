from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class RegisterIn(BaseModel):
    init_data: str  # Telegram WebApp initData

class UserOut(BaseModel):
    id: int
    tg_id: str
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    photo_url: Optional[str]
    likes_received: int = 0

class LocationIn(BaseModel):
    lat: float
    lon: float

class NearbyUser(BaseModel):
    id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    photo_url: Optional[str]
    distance_m: float
    likes_received: int

class LikeIn(BaseModel):
    target_user_id: int
    lat: float
    lon: float

class LikeOut(BaseModel):
    ok: bool
    message: str

class LeaderboardItem(BaseModel):
    user: UserOut
    likes_received: int

class LikeEvent(BaseModel):
    from_user_id: int
    to_user_id: int
    lat: float
    lon: float
    created_at: datetime

class ProfileOut(BaseModel):
    user: UserOut
    you_liked_them: bool
    they_liked_you: bool
    last_location: Optional[LocationIn] = None
    recent_likes: List[LikeEvent] = Field(default_factory=list)
