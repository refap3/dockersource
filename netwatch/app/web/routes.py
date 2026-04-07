from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device, Event
from app.schemas import DeviceOut, DeviceUpdate, EventOut

router = APIRouter()


@router.get("/api/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).order_by(Device.last_seen.desc()).all()


@router.get("/api/devices/{mac}", response_model=DeviceOut)
def get_device(mac: str, db: Session = Depends(get_db)):
    device = db.get(Device, mac.lower())
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.put("/api/devices/{mac}", response_model=DeviceOut)
def update_device(mac: str, update: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.get(Device, mac.lower())
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if update.name is not None:
        device.name = update.name
    if update.category is not None:
        device.category = update.category
        device.category_source = "manual"
    if update.known is not None:
        device.known = update.known
    if update.notify_online is not None:
        device.notify_online = update.notify_online
    if update.notify_offline is not None:
        device.notify_offline = update.notify_offline
    db.commit()
    db.refresh(device)
    return device


@router.get("/api/events", response_model=list[EventOut])
def list_events(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Event).order_by(Event.ts.desc()).limit(limit).all()


@router.post("/api/scan")
async def manual_scan():
    from app.scanner.engine import trigger_sweep
    count = await trigger_sweep()
    return {"found": count}
