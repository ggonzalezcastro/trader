from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketState
import asyncio, json, redis.asyncio as redis, asyncpg
from nats.aio.client import NATS

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, client_id: str):
        await ws.accept()
        self.active[client_id] = ws

    def disconnect(self, client_id: str):
        if client_id in self.active:
            del self.active[client_id]

    async def broadcast(self, msg: dict):
        for ws in self.active.values():
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json(msg)

manager = ConnectionManager()

@app.on_event("startup")
async def startup():
    app.state.redis = redis.from_url("redis://redis:6379/0")
    app.state.db = await asyncpg.create_pool("postgresql://bot:botpass123@timescaledb:5432/trading", min_size=1, max_size=5)
    app.state.nc = NATS()
    await app.state.nc.connect("nats://nats:4222")

@app.on_event("shutdown")
async def shutdown():
    await app.state.redis.close()
    await app.state.db.close()
    await app.state.nc.close()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws, str(id(ws)))
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            await manager.broadcast(msg)
    except Exception:
        manager.disconnect(str(id(ws)))

@app.get("/positions")
async def positions():
    return []

@app.get("/robots")
async def robots():
    return []