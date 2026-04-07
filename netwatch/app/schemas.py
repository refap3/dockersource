from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DeviceOut(BaseModel):
    mac: str
    ip: Optional[str]
    hostname: Optional[str]
    vendor: Optional[str]
    category: str
    category_source: str
    name: Optional[str]
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    online: bool
    known: bool
    notify_online: bool
    notify_offline: bool

    class Config:
        from_attributes = True


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    known: Optional[bool] = None
    notify_online: Optional[bool] = None
    notify_offline: Optional[bool] = None


class EventOut(BaseModel):
    id: int
    mac: str
    event_type: str
    detail: Optional[str]
    ts: datetime
    notified: bool

    class Config:
        from_attributes = True
