import yaml
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("/app/config.yml")


def _load() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Config file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


class _Section:
    def __init__(self, data: dict):
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class Config:
    def __init__(self):
        data = _load()
        s = data.get("scanner", {})
        self.network: str = s.get("network", "192.168.1.0/24")
        self.interface: str = s.get("interface", "eth0")
        self.interval_minutes: int = int(s.get("interval_minutes", 5))
        self.offline_threshold_minutes: int = int(s.get("offline_threshold_minutes", 15))

        n = data.get("notifications", {})
        self.webhook = n.get("webhook", {})
        self.telegram = n.get("telegram", {})
        self.smtp = n.get("smtp", {})

        a = data.get("alarms", {})
        self.alarm_new_device: bool = bool(a.get("new_device", True))
        self.alarm_known_online: bool = bool(a.get("known_device_online", True))
        self.alarm_known_offline: bool = bool(a.get("known_device_offline", False))

        self.known_devices: dict = data.get("known_devices", {}) or {}


_instance: Config | None = None


def get_config() -> Config:
    global _instance
    if _instance is None:
        _instance = Config()
    return _instance
