from mac_vendor_lookup import AsyncMacLookup, VendorNotFoundError

_lookup = AsyncMacLookup()

VENDOR_HINTS: dict[str, str] = {
    "raspberry pi": "iot",
    "synology": "nas",
    "qnap": "nas",
    "western digital": "nas",
    "tp-link": "router",
    "asus": "router",
    "ubiquiti": "router",
    "netgear": "router",
    "mikrotik": "router",
    "fritzbox": "router",
    "avm": "router",
    "brother": "printer",
    "canon": "printer",
    "hp inc": "printer",
    "hewlett packard": "printer",
    "epson": "printer",
    "samsung": "phone",
    "xiaomi": "phone",
    "huawei": "phone",
    "oneplus": "phone",
    "amazon": "iot",
    "google": "iot",
    "sonos": "iot",
    "philips": "iot",
    "ikea": "iot",
    "shelly": "iot",
    "espressif": "iot",
    "tuya": "iot",
    "intel": "pc",
    "dell": "pc",
    "lenovo": "pc",
    "microsoft": "pc",
}

HOSTNAME_HINTS: dict[str, str] = {
    "macbook": "laptop",
    "imac": "pc",
    "mac-mini": "pc",
    "macmini": "pc",
    "iphone": "phone",
    "ipad": "tablet",
    "android": "phone",
    "printer": "printer",
    "router": "router",
    "nas": "nas",
    "raspberrypi": "iot",
    "raspberry": "iot",
}


async def get_vendor(mac: str) -> str:
    try:
        return await _lookup.lookup(mac)
    except (VendorNotFoundError, Exception):
        return ""


def classify(vendor: str, hostname: str | None) -> str:
    h = (hostname or "").lower().replace("-", "").replace("_", "")
    for key, cat in HOSTNAME_HINTS.items():
        if key in h:
            return cat

    v = vendor.lower()
    if "apple" in v:
        # Apple makes Macs, phones, tablets — hostname gives the best hint
        if any(k in h for k in ("macbook", "imac", "mac")):
            return "laptop"
        if "ipad" in h:
            return "tablet"
        return "phone"

    for key, cat in VENDOR_HINTS.items():
        if key in v:
            return cat

    return "unknown"
