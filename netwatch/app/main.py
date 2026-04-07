import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_config
from app.database import init_db
from app.web.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cfg = get_config()
    log.info("netwatch starting — network=%s interface=%s", cfg.network, cfg.interface)

    from app.scanner.engine import run_sweep_loop, run_offline_checker, run_arp_sniffer, run_vendor_backfill

    await run_vendor_backfill()

    tasks = [
        asyncio.create_task(run_sweep_loop(), name="sweep"),
        asyncio.create_task(run_offline_checker(), name="offline_checker"),
        asyncio.create_task(run_arp_sniffer(), name="arp_sniffer"),
    ]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info("netwatch stopped")


app = FastAPI(title="netwatch", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory="/app/app/web/static"), name="static")


@app.get("/")
def index():
    return FileResponse("/app/app/web/static/index.html")
