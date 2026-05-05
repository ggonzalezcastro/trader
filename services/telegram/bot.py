import os, asyncio, json
from loguru import logger
from nats.aio.client import NATS

TG_TOKEN = os.getenv("TG_TOKEN", "")

async def main():
    if not TG_TOKEN:
        logger.warning("TG_TOKEN no configurado. Saliendo.")
        return

    nc = NATS()
    await nc.connect("nats://nats:4222")
    js = nc.jetstream()

    async def handler(msg):
        data = json.loads(msg.data)
        logger.info(f"Mensaje NATS: {data}")

    sub = await js.subscribe("alerts.*", handler=handler)
    logger.info("Telegram bot escuchando...")

    try:
        await asyncio.Future()
    finally:
        await nc.close()

if __name__ == "__main__":
    asyncio.run(main())