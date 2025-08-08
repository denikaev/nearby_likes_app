import os
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from dotenv import load_dotenv

from .db import Base, engine, SessionLocal
from .models import User, LocationPing, Like
from .schemas import (
    RegisterIn, UserOut, LocationIn, NearbyUser, LikeIn, LikeOut,
    LeaderboardItem, ProfileOut, LikeEvent
)
from .security import check_init_data
from .utils import (
    haversine_m, encode_geohash, NEARBY_METERS,
    like_cooldown_deadline, geohash_cooldown_deadline
)

# Подтягиваем локальный .env (на Render переменные берутся из Dashboard)
load_dotenv()

# ---------------- DB & APP ----------------
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nearby Likes MiniApp")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- WebApp UI ----------------
@app.get("/webapp", response_class=HTMLResponse)
def webapp_page(request: Request):
    return templates.TemplateResponse("webapp.html", {"request": request})

# ---------------- Auth (Telegram initData) ----------------
@app.post("/api/register", response_model=UserOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    data = check_init_data(payload.init_data)  # HMAC проверка по токену бота
    user_str = data.get("user")
    import json
    if not user_str:
        raise HTTPException(400, "No user in init data")
    tg_user = json.loads(user_str)

    tg_id = str(tg_user["id"])
    user = db.query(User).filter_by(tg_id=tg_id).first()
    if not user:
        user = User(tg_id=tg_id)
        db.add(user)

    user.username = tg_user.get("username")
    user.first_name = tg_user.get("first_name")
    user.last_name = tg_user.get("last_name")
    user.photo_url = tg_user.get("photo_url")
    db.commit()
    db.refresh(user)

    likes_count = db.query(func.count(Like.id)).filter(Like.to_user_id == user.id).scalar() or 0

    return UserOut(
        id=user.id, tg_id=user.tg_id, username=user.username, first_name=user.first_name,
        last_name=user.last_name, photo_url=user.photo_url, likes_received=likes_count
    )

# ---------------- Location heartbeat ----------------
@app.post("/api/heartbeat", response_model=UserOut)
def heartbeat(payload: LocationIn, request: Request, db: Session = Depends(get_db)):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(401, "Missing X-User-Id")
    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(401, "Unknown user")

    gh = encode_geohash(payload.lat, payload.lon)
    db.add(LocationPing(user_id=user.id, lat=payload.lat, lon=payload.lon, geohash=gh))
    db.commit()

    likes_count = db.query(func.count(Like.id)).filter(Like.to_user_id == user.id).scalar() or 0
    return UserOut(
        id=user.id, tg_id=user.tg_id, username=user.username, first_name=user.first_name,
        last_name=user.last_name, photo_url=user.photo_url, likes_received=likes_count
    )

# ---------------- Nearby (<= NEARBY_METERS) ----------------
@app.get("/api/nearby", response_model=List[NearbyUser])
def nearby(request: Request, lat: float, lon: float, db: Session = Depends(get_db)):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(401, "Missing X-User-Id")
    me = db.get(User, int(user_id))
    if not me:
        raise HTTPException(401, "Unknown user")

    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=5)

    sub = (
        db.query(LocationPing.user_id, func.max(LocationPing.created_at).label("max_ts"))
        .group_by(LocationPing.user_id)
        .subquery()
    )
    q = (
        db.query(LocationPing, User)
        .join(User, User.id == LocationPing.user_id)
        .join(sub, and_(sub.c.user_id == LocationPing.user_id, sub.c.max_ts == LocationPing.created_at))
        .filter(LocationPing.created_at >= cutoff)
        .filter(LocationPing.user_id != me.id)
    )

    out: List[NearbyUser] = []
    for ping, user in q:
        d = haversine_m(lat, lon, ping.lat, ping.lon)
        if d <= NEARBY_METERS:
            likes_count = db.query(func.count(Like.id)).filter(Like.to_user_id == user.id).scalar() or 0
            out.append(NearbyUser(
                id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                photo_url=user.photo_url,
                distance_m=round(d, 2),
                likes_received=likes_count
            ))
    out.sort(key=lambda x: x.distance_m)
    return out

# ---------------- Like ----------------
@app.post("/api/like", response_model=LikeOut)
def like_user(payload: LikeIn, request: Request, db: Session = Depends(get_db)):
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(401, "Missing X-User-Id")
    me = db.get(User, int(user_id))
    if not me:
        raise HTTPException(401, "Unknown user")
    if me.id == payload.target_user_id:
        raise HTTPException(400, "Нельзя лайкнуть себя")

    target = db.get(User, payload.target_user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")

    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=5)

    last_target_ping = (
        db.query(LocationPing)
        .filter(LocationPing.user_id == target.id, LocationPing.created_at >= cutoff)
        .order_by(LocationPing.created_at.desc())
        .first()
    )
    if not last_target_ping:
        raise HTTPException(400, "Цель не рядом (нет свежей геопозиции)")

    last_me_ping = (
        db.query(LocationPing)
        .filter(LocationPing.user_id == me.id, LocationPing.created_at >= cutoff)
        .order_by(LocationPing.created_at.desc())
        .first()
    )
    if not last_me_ping:
        raise HTTPException(400, "Обнови свою геопозицию")

    dist = haversine_m(last_me_ping.lat, last_me_ping.lon, last_target_ping.lat, last_target_ping.lon)
    if dist > NEARBY_METERS:
        raise HTTPException(400, "Должны быть на расстоянии ≤ 50 м")

    last_like = (
        db.query(Like)
        .filter(Like.from_user_id == me.id, Like.to_user_id == target.id)
        .order_by(Like.created_at.desc())
        .first()
    )
    from datetime import timezone
    if last_like and last_like.created_at.replace(tzinfo=timezone.utc) > like_cooldown_deadline():
        secs = int((last_like.created_at.replace(tzinfo=timezone.utc) - like_cooldown_deadline()).total_seconds())
        raise HTTPException(429, f"Повторный лайк этому пользователю будет доступен через ~{secs} сек.")

    gh = last_me_ping.geohash
    gh_deadline = geohash_cooldown_deadline()
    recent_same_cell = (
        db.query(Like)
        .join(LocationPing, Like.from_user_id == LocationPing.user_id)
        .filter(
            Like.from_user_id == me.id,
            Like.created_at >= gh_deadline,
            LocationPing.geohash == gh,
        )
        .first()
    )
    if recent_same_cell:
        raise HTTPException(429, "Слишком часто в одной точке. Подойди в другое место или подожди.")

    db.add(Like(from_user_id=me.id, to_user_id=target.id, lat=last_me_ping.lat, lon=last_me_ping.lon))
    db.commit()
    return LikeOut(ok=True, message="Лайк засчитан")

# ---------------- Leaderboard ----------------
@app.get("/api/leaderboard", response_model=List[LeaderboardItem])
def leaderboard(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(User, func.count(Like.id).label("score"))
        .outerjoin(Like, Like.to_user_id == User.id)
        .group_by(User.id)
        .order_by(desc("score"))
        .limit(limit)
        .all()
    )
    out: List[LeaderboardItem] = []
    for u, score in rows:
        out.append(LeaderboardItem(
            user=UserOut(
                id=u.id, tg_id=u.tg_id, username=u.username, first_name=u.first_name,
                last_name=u.last_name, photo_url=u.photo_url, likes_received=score or 0
            ),
            likes_received=score or 0
        ))
    return out

# ---------------- Profile ----------------
@app.get("/api/profile/{user_id}", response_model=ProfileOut)
def profile(user_id: int, request: Request, db: Session = Depends(get_db)):
    me_id = request.headers.get("X-User-Id")
    if not me_id:
        raise HTTPException(401, "Missing X-User-Id")
    me_id = int(me_id)

    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Not found")

    likes_to = db.query(func.count(Like.id)).filter(Like.to_user_id == u.id).scalar() or 0
    you_liked_them = db.query(Like).filter(Like.from_user_id == me_id, Like.to_user_id == u.id).first() is not None
    they_liked_you = db.query(Like).filter(Like.from_user_id == u.id, Like.to_user_id == me_id).first() is not None

    last_ping = (
        db.query(LocationPing)
        .filter(LocationPing.user_id == u.id)
        .order_by(LocationPing.created_at.desc())
        .first()
    )
    recent_likes = (
        db.query(Like)
        .filter((Like.from_user_id == u.id) | (Like.to_user_id == u.id))
        .order_by(Like.created_at.desc())
        .limit(20).all()
    )

    return ProfileOut(
        user=UserOut(
            id=u.id, tg_id=u.tg_id, username=u.username, first_name=u.first_name,
            last_name=u.last_name, photo_url=u.photo_url, likes_received=likes_to
        ),
        you_liked_them=you_liked_them,
        they_liked_you=they_liked_you,
        last_location=(LocationIn(lat=last_ping.lat, lon=last_ping.lon) if last_ping else None),
        recent_likes=[
            LikeEvent(
                from_user_id=lk.from_user_id, to_user_id=lk.to_user_id,
                lat=lk.lat, lon=lk.lon, created_at=lk.created_at
            ) for lk in recent_likes
        ]
    )

# ===================== Telegram bot via POLLING (no threads) =====================
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # https://<render>/webapp

if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set")

app.state.tg_app = None  # Application из python-telegram-bot

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton(text="Открыть Nearby Likes", web_app=WebAppInfo(url=WEBAPP_URL))]]
    if update.message:
        await update.message.reply_text(
            "Открой мини-апп, дай геолокацию и лайкай тех, кто реально рядом (≤ 50 м).",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )

@app.on_event("startup")
async def _start_bot():
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN is not set — бот не запустится (ок на dev).")
        return
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))

    # Запускаем бота в текущем event loop FastAPI (без потоков)
    await application.initialize()
    await application.start()
    # В PTB v20+ polling управляется через внутренний Updater
    await application.updater.start_polling()

    app.state.tg_app = application
    print("Telegram bot started (polling) in FastAPI loop.")

@app.on_event("shutdown")
async def _stop_bot():
    application = app.state.tg_app
    if application:
        try:
            await application.updater.stop()
        except Exception:
            pass
        await application.stop()
        await application.shutdown()
        app.state.tg_app = None
        print("Telegram bot stopped.")
# ==============================================================================
