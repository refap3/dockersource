import asyncio
import smtplib
from email.mime.text import MIMEText


def _send_sync(title: str, body: str, cfg: dict):
    msg = MIMEText(body)
    msg["Subject"] = title
    msg["From"] = cfg["from_addr"]
    msg["To"] = cfg["to_addr"]

    with smtplib.SMTP(cfg["host"], int(cfg["port"])) as s:
        s.starttls()
        s.login(cfg["username"], cfg["password"])
        s.sendmail(cfg["from_addr"], [cfg["to_addr"]], msg.as_string())


async def send(title: str, body: str, cfg: dict):
    await asyncio.to_thread(_send_sync, title, body, cfg)
