import httpx


async def send(title: str, body: str, cfg: dict):
    url = cfg["url"]
    method = cfg.get("method", "POST").upper()
    headers = cfg.get("headers", {})
    payload = {"title": title, "message": body}

    async with httpx.AsyncClient() as client:
        if method == "GET":
            await client.get(url, params=payload, headers=headers, timeout=10)
        else:
            await client.post(url, json=payload, headers=headers, timeout=10)
