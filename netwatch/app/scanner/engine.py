import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_config
from app.database import SessionLocal
from app.models import Device, Event
from app.scanner.arp_sniffer import ArpEvent, start_arp_thread
from app.scanner.nmap_sweep import DeviceInfo, sweep
from app.scanner.vendor import classify, get_vendor

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
_db_lock = asyncio.Lock()
_arp_queue: asyncio.Queue = asyncio.Queue()


def _apply_known_device_config(device: Device, cfg_entry: dict):
    """Apply config.yml known_devices overrides to a device record."""
    if "name" in cfg_entry:
        device.name = cfg_entry["name"]
    if "category" in cfg_entry:
        device.category = cfg_entry["category"]
        device.category_source = "config"
    if "notify_online" in cfg_entry:
        device.notify_online = cfg_entry["notify_online"]
    if "notify_offline" in cfg_entry:
        device.notify_offline = cfg_entry["notify_offline"]
    device.known = True


async def _process_device(info: DeviceInfo | ArpEvent, db: Session):
    from app.notifications.dispatcher import dispatch

    cfg = get_config()
    mac = info.mac.lower()
    ip = info.ip

    existing: Device | None = db.get(Device, mac)
    now = datetime.utcnow()

    if existing is None:
        # New device
        vendor = await get_vendor(mac)
        hostname = getattr(info, "hostname", None)
        category = classify(vendor, hostname)

        device = Device(
            mac=mac,
            ip=ip,
            hostname=hostname,
            vendor=vendor,
            category=category,
            category_source="auto",
            first_seen=now,
            last_seen=now,
            online=True,
            known=False,
            notify_online=True,
            notify_offline=False,
            known_ips=json.dumps([ip]),
        )

        # Apply static config overrides
        cfg_entry = cfg.known_devices.get(mac, {})
        if cfg_entry:
            _apply_known_device_config(device, cfg_entry)

        db.add(device)

        event = Event(
            mac=mac,
            event_type="new_device",
            detail=json.dumps({"ip": ip, "vendor": vendor}),
            ts=now,
            notified=False,
        )
        db.add(event)
        db.commit()

        if cfg.alarm_new_device:
            await dispatch(event, device)
            event.notified = True
            db.commit()

        log.info("New device: %s (%s) [%s]", mac, ip, vendor)

    else:
        # Apply any config overrides that may have changed
        cfg_entry = cfg.known_devices.get(mac, {})
        if cfg_entry:
            _apply_known_device_config(existing, cfg_entry)

        changed = False

        if not existing.online:
            existing.online = True
            existing.last_seen = now
            changed = True

            event = Event(
                mac=mac,
                event_type="came_online",
                detail=json.dumps({"ip": ip}),
                ts=now,
                notified=False,
            )
            db.add(event)
            db.commit()

            if existing.notify_online and cfg.alarm_known_online:
                await dispatch(event, existing)
                event.notified = True
                db.commit()

            log.info("Device came online: %s (%s)", mac, ip)

        else:
            existing.last_seen = now

        if existing.ip != ip:
            old_ip = existing.ip
            existing.ip = ip
            changed = True
            # Only emit ip_changed if this IP has never been seen for this device
            known_ips = json.loads(existing.known_ips or "[]")
            if ip not in known_ips:
                known_ips.append(ip)
                existing.known_ips = json.dumps(known_ips)
                ev = Event(
                    mac=mac,
                    event_type="ip_changed",
                    detail=json.dumps({"old_ip": old_ip, "new_ip": ip}),
                    ts=now,
                    notified=True,
                )
                db.add(ev)
                log.info("IP changed (new): %s %s → %s", mac, old_ip, ip)
            else:
                existing.known_ips = json.dumps(known_ips)
                log.debug("IP oscillation suppressed: %s %s → %s", mac, old_ip, ip)

        if changed or True:
            db.commit()


async def run_vendor_backfill():
    """On startup, re-lookup vendor/category for any devices that have none."""
    async with _db_lock:
        db = SessionLocal()
        try:
            missing = (
                db.query(Device)
                .filter((Device.vendor == None) | (Device.vendor == ""))  # noqa: E711
                .all()
            )
            if not missing:
                return
            log.info("Backfilling vendor for %d devices with no vendor info", len(missing))
            for device in missing:
                vendor = await get_vendor(device.mac)
                if vendor:
                    device.vendor = vendor
                    if device.category_source == "auto":
                        device.category = classify(vendor, device.hostname)
                    log.info("Backfilled %s -> %s [%s]", device.mac, vendor, device.category)
            db.commit()
        finally:
            db.close()


async def run_sweep_loop():
    cfg = get_config()
    loop = asyncio.get_event_loop()
    while True:
        try:
            log.info("Starting nmap sweep of %s", cfg.network)
            results = await loop.run_in_executor(_executor, sweep, cfg.network)
            async with _db_lock:
                db = SessionLocal()
                try:
                    for info in results:
                        await _process_device(info, db)
                finally:
                    db.close()
        except Exception as e:
            log.error("Sweep error: %s", e)
        await asyncio.sleep(cfg.interval_minutes * 60)


async def run_offline_checker():
    """Mark devices offline when they haven't been seen for threshold minutes."""
    from app.notifications.dispatcher import dispatch

    cfg = get_config()
    while True:
        await asyncio.sleep(60)
        try:
            threshold = datetime.utcnow() - timedelta(minutes=cfg.offline_threshold_minutes)
            async with _db_lock:
                db = SessionLocal()
                try:
                    stale = (
                        db.query(Device)
                        .filter(Device.online == True, Device.last_seen < threshold)  # noqa: E712
                        .all()
                    )
                    now = datetime.utcnow()
                    for device in stale:
                        device.online = False
                        event = Event(
                            mac=device.mac,
                            event_type="went_offline",
                            detail=json.dumps({"ip": device.ip}),
                            ts=now,
                            notified=False,
                        )
                        db.add(event)
                        db.commit()

                        if device.notify_offline and cfg.alarm_known_offline:
                            await dispatch(event, device)
                            event.notified = True
                            db.commit()

                        log.info("Device went offline: %s (%s)", device.mac, device.ip)
                finally:
                    db.close()
        except Exception as e:
            log.error("Offline checker error: %s", e)


async def run_arp_sniffer():
    cfg = get_config()
    loop = asyncio.get_event_loop()
    start_arp_thread(_arp_queue, loop, cfg.interface)
    while True:
        try:
            event: ArpEvent = await asyncio.wait_for(_arp_queue.get(), timeout=5.0)
            async with _db_lock:
                db = SessionLocal()
                try:
                    await _process_device(event, db)
                finally:
                    db.close()
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            log.error("ARP handler error: %s", e)


async def trigger_sweep():
    """Manual sweep trigger from API."""
    cfg = get_config()
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(_executor, sweep, cfg.network)
    async with _db_lock:
        db = SessionLocal()
        try:
            for info in results:
                await _process_device(info, db)
        finally:
            db.close()
    return len(results)
