import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
import json
import boto3

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
SEAT_THRESHOLD = int(os.environ.get("SEAT_THRESHOLD", "10"))
sns = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "ap-south-1")) if SNS_TOPIC_ARN else None

def notify_if_low(event_id: int, title: str, remaining: int):
    if sns and remaining < SEAT_THRESHOLD:
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=json.dumps({
                    "event_id": event_id,
                    "title": title,
                    "seats_available": remaining,
                    "threshold": SEAT_THRESHOLD,
                }),
            )
        except Exception as e:
            print(f"SNS publish failed: {e}")

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)          # Event ID
    title = Column(String, nullable=False)
    venue = Column(String, nullable=False)
    date_time = Column(DateTime, nullable=False)
    ticket_price = Column(Float, nullable=False)
    capacity = Column(Integer, nullable=False)
    seats_available = Column(Integer, nullable=False)

Base.metadata.create_all(engine)   # creates the table on first start

def as_dict(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}

app = FastAPI(title="Event Service",
              docs_url="/api/events/docs",
              openapi_url="/api/events/openapi.json")

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

class EventIn(BaseModel):
    title: str
    venue: str
    date_time: datetime
    ticket_price: float
    capacity: int
    seats_available: int

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/events", status_code=201)
def create_event(body: EventIn):
    with SessionLocal() as db:
        ev = Event(**body.model_dump())
        db.add(ev); db.commit(); db.refresh(ev)
        return as_dict(ev)

@app.get("/api/events")
def list_events():
    with SessionLocal() as db:
        return [as_dict(e) for e in db.query(Event).all()]

@app.get("/api/events/{event_id}")
def get_event(event_id: int):
    with SessionLocal() as db:
        ev = db.get(Event, event_id)
        if not ev:
            raise HTTPException(404, "Event not found")
        return as_dict(ev)

@app.put("/api/events/{event_id}")
def update_event(event_id: int, body: EventIn):
    with SessionLocal() as db:
        ev = db.get(Event, event_id)
        if not ev:
            raise HTTPException(404, "Event not found")
        for k, v in body.model_dump().items():
            setattr(ev, k, v)
        db.commit(); db.refresh(ev)
        return as_dict(ev)

@app.post("/api/events/{event_id}/reserve")
def reserve_seats(event_id: int, tickets: int = 1):
    with SessionLocal() as db:
        ev = db.get(Event, event_id)
        if not ev:
            raise HTTPException(404, "Event not found")
        if ev.seats_available < tickets:
            raise HTTPException(409, "Not enough seats available")
        ev.seats_available -= tickets
        db.commit()
        remaining = ev.seats_available
        title = ev.title
    notify_if_low(event_id, title, remaining)
    return {"event_id": event_id, "seats_available": remaining}