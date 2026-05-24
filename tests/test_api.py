from datetime import datetime, timedelta
from db.models import User, Class, Booking, BookingStatus, Subscription, SubscriptionType

UID = 111_000_001  # тестовый Telegram ID


# ── helpers ──────────────────────────────────────────────────────

async def make_user(db, tg_id=UID, name="Анна Тест"):
    u = User(id=tg_id, full_name=name, is_active=True)
    db.add(u)
    await db.commit()
    return u


async def make_class(db, days=1, spots=10, title="Bachata"):
    c = Class(
        title=title, trainer="Maria",
        starts_at=datetime.utcnow() + timedelta(days=days, hours=10),
        max_spots=spots, location="Студия А",
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def make_sub(db, user_id=UID, classes_left=8):
    s = Subscription(
        user_id=user_id, sub_type=SubscriptionType.PACK_8,
        classes_left=classes_left,
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    db.add(s)
    await db.commit()
    return s


HDR = {"X-User-Id": str(UID)}


# ── /home ─────────────────────────────────────────────────────────

async def test_home_unknown_user(api_client):
    r = await api_client.get("/miniapp/api/home", headers={"X-User-Id": "999"})
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == ""
    assert d["classes_left"] == 0


async def test_home_known_user_no_sub(api_client, db):
    await make_user(db)
    r = await api_client.get("/miniapp/api/home", headers=HDR)
    d = r.json()
    assert "Анна" in d["name"]
    assert d["classes_left"] == 0


async def test_home_with_subscription(api_client, db):
    await make_user(db)
    await make_sub(db, classes_left=5)
    r = await api_client.get("/miniapp/api/home", headers=HDR)
    assert r.json()["classes_left"] == 5


# ── /schedule ────────────────────────────────────────────────────

async def test_schedule_empty_month(api_client):
    r = await api_client.get("/miniapp/api/schedule", params={"year": 2030, "month": 1})
    assert r.status_code == 200
    assert r.json()["classes"] == []


async def test_schedule_shows_class_dot(api_client, db):
    cls = await make_class(db, days=2)
    y, m = cls.starts_at.year, cls.starts_at.month
    r = await api_client.get("/miniapp/api/schedule", params={"year": y, "month": m})
    dates = [c["date"] for c in r.json()["classes"]]
    assert cls.starts_at.strftime("%Y-%m-%d") in dates


async def test_day_no_classes(api_client):
    r = await api_client.get("/miniapp/api/schedule/day", params={"date": "2030-01-15"})
    assert r.status_code == 200
    assert r.json()["classes"] == []


async def test_day_returns_class(api_client, db):
    cls = await make_class(db, days=3)
    date_str = cls.starts_at.strftime("%Y-%m-%d")
    r = await api_client.get("/miniapp/api/schedule/day",
                              params={"date": date_str}, headers=HDR)
    items = r.json()["classes"]
    assert len(items) == 1
    assert items[0]["title"] == "Bachata"
    assert items[0]["free_spots"] == 10
    assert items[0]["is_booked"] is False


# ── /book ─────────────────────────────────────────────────────────

async def test_book_no_auth(api_client):
    r = await api_client.post("/miniapp/api/book",
                               json={"class_id": 1},
                               headers={"X-User-Id": "0"})
    assert r.json()["ok"] is False


async def test_book_no_subscription(api_client, db):
    await make_user(db)
    cls = await make_class(db)
    r = await api_client.post("/miniapp/api/book",
                               json={"class_id": cls.id}, headers=HDR)
    assert r.json()["ok"] is False
    assert "абонемент" in r.json()["error"].lower()


async def test_book_success(api_client, db):
    await make_user(db)
    await make_sub(db)
    cls = await make_class(db)
    r = await api_client.post("/miniapp/api/book",
                               json={"class_id": cls.id}, headers=HDR)
    assert r.json()["ok"] is True


async def test_book_already_booked(api_client, db):
    await make_user(db)
    await make_sub(db, classes_left=8)
    cls = await make_class(db)
    await api_client.post("/miniapp/api/book", json={"class_id": cls.id}, headers=HDR)
    r = await api_client.post("/miniapp/api/book", json={"class_id": cls.id}, headers=HDR)
    assert r.json()["ok"] is False


async def test_book_no_spots(api_client, db):
    await make_user(db)
    await make_sub(db)
    cls = await make_class(db, spots=0)
    r = await api_client.post("/miniapp/api/book",
                               json={"class_id": cls.id}, headers=HDR)
    assert r.json()["ok"] is False


# ── /bookings & /cancel ───────────────────────────────────────────

async def test_bookings_empty(api_client, db):
    await make_user(db)
    r = await api_client.get("/miniapp/api/bookings", headers=HDR)
    assert r.json()["bookings"] == []


async def test_cancel_booking(api_client, db):
    await make_user(db)
    await make_sub(db)
    cls = await make_class(db)
    await api_client.post("/miniapp/api/book", json={"class_id": cls.id}, headers=HDR)

    bks = (await api_client.get("/miniapp/api/bookings", headers=HDR)).json()["bookings"]
    assert len(bks) == 1

    r = await api_client.post("/miniapp/api/cancel",
                               json={"booking_id": bks[0]["booking_id"]})
    assert r.json()["ok"] is True

    bks_after = (await api_client.get("/miniapp/api/bookings", headers=HDR)).json()["bookings"]
    assert bks_after == []


# ── /subscription ─────────────────────────────────────────────────

async def test_subscription_no_user(api_client):
    r = await api_client.get("/miniapp/api/subscription", headers={"X-User-Id": "999"})
    d = r.json()
    assert d["classes_left"] == 0
    assert d["total"] == 0


async def test_subscription_active(api_client, db):
    await make_user(db)
    await make_sub(db, classes_left=6)
    r = await api_client.get("/miniapp/api/subscription", headers=HDR)
    d = r.json()
    assert d["classes_left"] == 6
    assert d["total"] == 8   # PACK_8
    assert d["used"] == 2
