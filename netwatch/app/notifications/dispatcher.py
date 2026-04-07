import logging

from app.config import get_config
from app.models import Device, Event

log = logging.getLogger(__name__)


async def dispatch(event: Event, device: Device):
    cfg = get_config()
    title = _make_title(event, device)
    body = _make_body(event, device)

    if cfg.webhook.get("enabled"):
        try:
            from app.notifications.webhook import send as wh_send
            await wh_send(title, body, cfg.webhook)
        except Exception as e:
            log.error("Webhook notification failed: %s", e)

    if cfg.telegram.get("enabled"):
        try:
            from app.notifications.telegram import send as tg_send
            await tg_send(title, body, cfg.telegram)
        except Exception as e:
            log.error("Telegram notification failed: %s", e)

    if cfg.smtp.get("enabled"):
        try:
            from app.notifications.smtp_notifier import send as smtp_send
            await smtp_send(title, body, cfg.smtp)
        except Exception as e:
            log.error("SMTP notification failed: %s", e)


def _make_title(event: Event, device: Device) -> str:
    label = device.name or device.hostname or device.mac
    type_labels = {
        "new_device": f"New device on network: {label}",
        "came_online": f"Device online: {label}",
        "went_offline": f"Device offline: {label}",
        "ip_changed": f"IP changed: {label}",
    }
    return type_labels.get(event.event_type, f"netwatch: {event.event_type}")


def _make_body(event: Event, device: Device) -> str:
    lines = [
        f"MAC: {device.mac}",
        f"IP:  {device.ip}",
    ]
    if device.vendor:
        lines.append(f"Vendor: {device.vendor}")
    if device.category:
        lines.append(f"Category: {device.category}")
    return "\n".join(lines)
