import httpx


async def send(title: str, body: str, cfg: dict):
    token = cfg["bot_token"]
    chat_id = cfg["chat_id"]
    text = f"*{title}*\n{body}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
