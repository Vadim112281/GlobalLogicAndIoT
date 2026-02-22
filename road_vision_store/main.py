from __future__ import annotations

from datetime import datetime
from typing import List, Set, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    Integer, String, Float, DateTime,
    select, insert, update, delete
)

import config

# -------------------------
# DB setup
# -------------------------
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
metadata = MetaData()

processed_agent_data = Table(
    "processed_agent_data",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("road_state", String, nullable=False),
    Column("x", Float),
    Column("y", Float),
    Column("z", Float),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime),
)

# -------------------------
# Pydantic models
# -------------------------
class AccelerometerData(BaseModel):
    x: float
    y: float
    z: float

class GpsData(BaseModel):
    latitude: float
    longitude: float

class AgentData(BaseModel):
    accelerometer: AccelerometerData
    gps: GpsData
    timestamp: datetime

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(v)
        except Exception:
            raise ValueError("Invalid timestamp формат. Очікується ISO 8601, напр: 2026-02-22T12:00:00")

class ProcessedAgentData(BaseModel):
    road_state: str
    agent_data: AgentData

class ProcessedAgentDataInDB(BaseModel):
    id: int
    road_state: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[datetime] = None

# -------------------------
# App + WebSocket
# -------------------------
app = FastAPI(title="Road Vision Store API", version="1.0.0")

subscribers: Set[WebSocket] = set()

@app.websocket("/ws/")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    subscribers.add(ws)
    try:
        while True:
            # клієнт може слати ping/текст, щоб тримати канал живим
            await ws.receive_text()
    except WebSocketDisconnect:
        subscribers.discard(ws)
    except Exception:
        subscribers.discard(ws)

async def ws_broadcast(payload: dict):
    dead = []
    for ws in list(subscribers):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        subscribers.discard(ws)

def row_to_model(row) -> ProcessedAgentDataInDB:
    return ProcessedAgentDataInDB(
        id=row.id,
        road_state=row.road_state,
        x=row.x,
        y=row.y,
        z=row.z,
        latitude=row.latitude,
        longitude=row.longitude,
        timestamp=row.timestamp,
    )

# -------------------------
# CRUD
# -------------------------
@app.post("/processed_agent_data/", response_model=list[ProcessedAgentDataInDB])
async def create_processed_agent_data(items: List[ProcessedAgentData]):
    if not items:
        return []

    rows = []
    for it in items:
        rows.append({
            "road_state": it.road_state,
            "x": it.agent_data.accelerometer.x,
            "y": it.agent_data.accelerometer.y,
            "z": it.agent_data.accelerometer.z,
            "latitude": it.agent_data.gps.latitude,
            "longitude": it.agent_data.gps.longitude,
            "timestamp": it.agent_data.timestamp,
        })

    with engine.begin() as conn:
        created_rows = conn.execute(
            insert(processed_agent_data).returning(processed_agent_data),
            rows
        ).fetchall()

    created = [row_to_model(r) for r in created_rows]

    await ws_broadcast({
        "type": "created",
        "items": [c.model_dump(mode="json") for c in created],
    })

    return created

@app.get("/processed_agent_data/", response_model=list[ProcessedAgentDataInDB])
def list_processed_agent_data():
    with engine.begin() as conn:
        rows = conn.execute(
            select(processed_agent_data).order_by(processed_agent_data.c.id)
        ).fetchall()
    return [row_to_model(r) for r in rows]

@app.get("/processed_agent_data/{item_id}", response_model=ProcessedAgentDataInDB)
def read_processed_agent_data(item_id: int):
    with engine.begin() as conn:
        row = conn.execute(
            select(processed_agent_data).where(processed_agent_data.c.id == item_id)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    return row_to_model(row)

@app.put("/processed_agent_data/{item_id}", response_model=ProcessedAgentDataInDB)
async def update_processed_agent_data(item_id: int, data: ProcessedAgentData):
    values = {
        "road_state": data.road_state,
        "x": data.agent_data.accelerometer.x,
        "y": data.agent_data.accelerometer.y,
        "z": data.agent_data.accelerometer.z,
        "latitude": data.agent_data.gps.latitude,
        "longitude": data.agent_data.gps.longitude,
        "timestamp": data.agent_data.timestamp,
    }

    with engine.begin() as conn:
        row = conn.execute(
            update(processed_agent_data)
            .where(processed_agent_data.c.id == item_id)
            .values(**values)
            .returning(processed_agent_data)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    model = row_to_model(row)

    await ws_broadcast({
        "type": "updated",
        "item": model.model_dump(mode="json"),
    })

    return model

@app.delete("/processed_agent_data/{item_id}", response_model=ProcessedAgentDataInDB)
async def delete_processed_agent_data(item_id: int):
    with engine.begin() as conn:
        row = conn.execute(
            delete(processed_agent_data)
            .where(processed_agent_data.c.id == item_id)
            .returning(processed_agent_data)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    model = row_to_model(row)

    await ws_broadcast({
        "type": "deleted",
        "id": model.id,
    })

    return model