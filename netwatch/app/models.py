from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, Text
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    mac = Column(Text, primary_key=True)
    ip = Column(Text)
    hostname = Column(Text)
    vendor = Column(Text)
    category = Column(Text, default="unknown")
    category_source = Column(Text, default="auto")   # "auto" | "manual"
    name = Column(Text)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    online = Column(Boolean, default=True)
    known = Column(Boolean, default=False)
    notify_online = Column(Boolean, default=True)
    notify_offline = Column(Boolean, default=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(Text, index=True)
    event_type = Column(Text)   # new_device | came_online | went_offline | ip_changed
    detail = Column(Text)       # JSON string
    ts = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)
