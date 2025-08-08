from sqlalchemy import Column, Integer, String, DateTime, Float, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)           # internal ID
    tg_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    locations = relationship("LocationPing", back_populates="user", cascade="all, delete")
    likes_given = relationship("Like", back_populates="from_user", foreign_keys="Like.from_user_id")
    likes_received = relationship("Like", back_populates="to_user", foreign_keys="Like.to_user_id")

class LocationPing(Base):
    __tablename__ = "location_pings"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    geohash = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="locations")

class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    to_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="likes_given")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="likes_received")
    __table_args__ = (
        UniqueConstraint("from_user_id", "to_user_id", name="uq_like_once"),
    )
