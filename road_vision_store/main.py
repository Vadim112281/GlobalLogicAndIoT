from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    insert,
    select,
    text,
    update,
)

import config


def calculate_repair_cost(length: float, width: float, depth: float) -> float:
    volume = length * width * depth
    base_service = 1500
    material_price = 0.8
    difficulty = 1.5 if depth > 5 else 1.0
    return round((base_service + (volume * material_price)) * difficulty, 2)


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
    Column("source", String, nullable=False, server_default="sensor"),
    Column("x", Float),
    Column("y", Float),
    Column("z", Float),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime),
    Column("length", Float),
    Column("width", Float),
    Column("depth", Float),
    Column("repair_cost", Float),
)


def ensure_schema() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS processed_agent_data (
            id SERIAL PRIMARY KEY,
            road_state VARCHAR(255) NOT NULL,
            source VARCHAR(50) NOT NULL DEFAULT 'sensor',
            x DOUBLE PRECISION,
            y DOUBLE PRECISION,
            z DOUBLE PRECISION,
            latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION,
            timestamp TIMESTAMP,
            length DOUBLE PRECISION,
            width DOUBLE PRECISION,
            depth DOUBLE PRECISION,
            repair_cost DOUBLE PRECISION
        )
        """,
        "ALTER TABLE processed_agent_data ADD COLUMN IF NOT EXISTS source VARCHAR(50) NOT NULL DEFAULT 'sensor'",
        "ALTER TABLE processed_agent_data ADD COLUMN IF NOT EXISTS length DOUBLE PRECISION",
        "ALTER TABLE processed_agent_data ADD COLUMN IF NOT EXISTS width DOUBLE PRECISION",
        "ALTER TABLE processed_agent_data ADD COLUMN IF NOT EXISTS depth DOUBLE PRECISION",
        "ALTER TABLE processed_agent_data ADD COLUMN IF NOT EXISTS repair_cost DOUBLE PRECISION",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


ensure_schema()
metadata.create_all(engine)


# -------------------------
# Pydantic models
# -------------------------
class AccelerometerData(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


class GpsData(BaseModel):
    latitude: float
    longitude: float


class DimensionsData(BaseModel):
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    depth: float = Field(gt=0)


class AgentData(BaseModel):
    accelerometer: Optional[AccelerometerData] = None
    gps: GpsData
    timestamp: datetime

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except Exception as exc:
            raise ValueError(
                "Invalid timestamp формат. Очікується ISO 8601, напр: 2026-02-22T12:00:00"
            ) from exc


class ProcessedAgentData(BaseModel):
    road_state: str
    agent_data: AgentData
    source: str = "sensor"
    dimensions: Optional[DimensionsData] = None


class ProcessedAgentDataInDB(BaseModel):
    id: int
    road_state: str
    source: str = "sensor"
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[datetime] = None
    length: Optional[float] = None
    width: Optional[float] = None
    depth: Optional[float] = None
    repair_cost: Optional[float] = None


def payload_to_row(item: ProcessedAgentData) -> dict:
    accelerometer = item.agent_data.accelerometer or AccelerometerData()
    dimensions = item.dimensions
    repair_cost = None

    if dimensions is not None:
        repair_cost = calculate_repair_cost(
            dimensions.length,
            dimensions.width,
            dimensions.depth,
        )

    return {
        "road_state": item.road_state,
        "source": item.source,
        "x": accelerometer.x,
        "y": accelerometer.y,
        "z": accelerometer.z,
        "latitude": item.agent_data.gps.latitude,
        "longitude": item.agent_data.gps.longitude,
        "timestamp": item.agent_data.timestamp,
        "length": dimensions.length if dimensions else None,
        "width": dimensions.width if dimensions else None,
        "depth": dimensions.depth if dimensions else None,
        "repair_cost": repair_cost,
    }


# -------------------------
# App + WebSocket
# -------------------------
app = FastAPI(title="Road Vision Store API", version="1.1.0")

subscribers: Set[WebSocket] = set()


@app.websocket("/ws/")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    subscribers.add(ws)
    try:
        while True:
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
        source=row.source or "sensor",
        x=row.x,
        y=row.y,
        z=row.z,
        latitude=row.latitude,
        longitude=row.longitude,
        timestamp=row.timestamp,
        length=row.length,
        width=row.width,
        depth=row.depth,
        repair_cost=row.repair_cost,
    )


# -------------------------
# CRUD
# -------------------------
@app.post("/processed_agent_data/", response_model=list[ProcessedAgentDataInDB])
async def create_processed_agent_data(items: List[ProcessedAgentData]):
    if not items:
        return []

    rows = [payload_to_row(item) for item in items]

    with engine.begin() as conn:
        created_rows = conn.execute(
            insert(processed_agent_data).returning(processed_agent_data),
            rows,
        ).fetchall()

    created = [row_to_model(row) for row in created_rows]

    await ws_broadcast(
        {
            "type": "created",
            "items": [item.model_dump(mode="json") for item in created],
        }
    )

    return created


@app.get("/processed_agent_data/", response_model=list[ProcessedAgentDataInDB])
def list_processed_agent_data():
    with engine.begin() as conn:
        rows = conn.execute(
            select(processed_agent_data).order_by(processed_agent_data.c.id)
        ).fetchall()
    return [row_to_model(row) for row in rows]


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
    values = payload_to_row(data)

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

    await ws_broadcast(
        {
            "type": "updated",
            "item": model.model_dump(mode="json"),
        }
    )

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

    await ws_broadcast(
        {
            "type": "deleted",
            "id": model.id,
        }
    )

    return model