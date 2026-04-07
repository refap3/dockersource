import logging
from dataclasses import dataclass

import nmap

log = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    ip: str
    mac: str
    hostname: str | None


def sweep(network: str) -> list[DeviceInfo]:
    """Run nmap ping scan and return discovered devices with MACs."""
    nm = nmap.PortScanner()
    try:
        nm.scan(hosts=network, arguments="-sn --host-timeout 10s")
    except Exception as e:
        log.error("nmap scan failed: %s", e)
        return []

    results = []
    for host in nm.all_hosts():
        try:
            mac = nm[host]["addresses"].get("mac", "").lower()
            hostname = None
            hostnames = nm[host].get("hostnames", [])
            if hostnames:
                hostname = hostnames[0].get("name") or None
            if mac:
                results.append(DeviceInfo(ip=host, mac=mac, hostname=hostname))
        except Exception as e:
            log.debug("Skipping host %s: %s", host, e)

    log.info("nmap sweep found %d devices with MACs on %s", len(results), network)
    return results
