import asyncio
import logging
import threading
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ArpEvent:
    ip: str
    mac: str


def _start_sniffer(queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, iface: str):
    """Run scapy ARP sniffer in a background thread, pushing events to asyncio queue."""
    try:
        from scapy.all import ARP, sniff  # type: ignore

        def handle(pkt):
            if pkt.haslayer(ARP) and pkt[ARP].op == 1:  # ARP who-has (request)
                mac = pkt[ARP].hwsrc.lower()
                ip = pkt[ARP].psrc
                # Skip ARP probes (DHCP conflict detection uses 0.0.0.0 source)
                if mac and mac != "00:00:00:00:00:00" and ip != "0.0.0.0":
                    asyncio.run_coroutine_threadsafe(
                        queue.put(ArpEvent(ip=ip, mac=mac)), loop
                    )

        log.info("ARP sniffer starting on interface %s", iface)
        sniff(filter="arp", prn=handle, store=0, iface=iface)
    except Exception as e:
        log.error("ARP sniffer error: %s", e)


def start_arp_thread(queue: asyncio.Queue, loop: asyncio.AbstractEventLoop, iface: str):
    t = threading.Thread(target=_start_sniffer, args=(queue, loop, iface), daemon=True)
    t.start()
    return t
