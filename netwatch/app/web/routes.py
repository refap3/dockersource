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
    if update.note is not None:
        device.note = update.note[:40]
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


@router.post("/api/check-status")
async def check_all_status(db: Session = Depends(get_db)):
    """Ping every known device concurrently and update online/offline immediately."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime
    import nmap

    devices = db.query(Device).filter(Device.ip != None).all()  # noqa: E711
    executor = ThreadPoolExecutor(max_workers=20)
    loop = asyncio.get_event_loop()

    def ping_one(ip):
        try:
            nm = nmap.PortScanner()
            nm.scan(hosts=ip, arguments="-sn --host-timeout 5s")
            return ip, ip in nm.all_hosts() and nm[ip].state() == "up"
        except Exception:
            return ip, False

    results = await asyncio.gather(
        *[loop.run_in_executor(executor, ping_one, d.ip) for d in devices]
    )

    now = datetime.utcnow()
    went_offline = went_online = 0
    ip_map = {d.ip: d for d in devices}
    for ip, up in results:
        device = ip_map.get(ip)
        if not device:
            continue
        if up and not device.online:
            device.online = True
            device.last_seen = now
            went_online += 1
        elif not up and device.online:
            device.online = False
            went_offline += 1
        elif up:
            device.last_seen = now

    db.commit()
    return {"checked": len(devices), "went_online": went_online, "went_offline": went_offline}


@router.post("/api/ping/{ip}")
async def ping_host(ip: str, db: Session = Depends(get_db)):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime
    import nmap

    loop = asyncio.get_event_loop()

    def do_ping():
        nm = nmap.PortScanner()
        nm.scan(hosts=ip, arguments="-sn --host-timeout 5s")
        up = ip in nm.all_hosts() and nm[ip].state() == "up"
        return up

    up = await loop.run_in_executor(ThreadPoolExecutor(max_workers=1), do_ping)

    device = db.query(Device).filter(Device.ip == ip).order_by(Device.last_seen.desc()).first()
    if device:
        now = datetime.utcnow()
        if up:
            device.online = True
            device.last_seen = now
        else:
            device.online = False
        db.commit()
        db.refresh(device)
        return {"online": up, "mac": device.mac, "ip": ip, "name": device.name, "hostname": device.hostname}

    return {"online": up, "mac": None, "ip": ip, "name": None, "hostname": None}
