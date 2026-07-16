import os
from datetime import datetime, timezone
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

EVENT_SERVICE_URL = os.environ.get("EVENT_SERVICE_URL", "http://event-service")

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Registration(Base):
    __tablename__ = "registrations"
    id = Column(Integer, primary_key=True)          # Registration ID
    event_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    ticket_count = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)

def as_dict(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}

app = FastAPI(title="Registration Service",
              docs_url="/api/registrations/docs",
              openapi_url="/api/registrations/openapi.json")

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

class RegistrationIn(BaseModel):
    event_id: int
    name: str
    email: str
    ticket_count: int = 1

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/registrations", status_code=201)
def create_registration(body: RegistrationIn):
    # 1) Reserve seats via the Event Service over cluster DNS
    try:
        r = httpx.post(
            f"{EVENT_SERVICE_URL}/api/events/{body.event_id}/reserve",
            params={"tickets": body.ticket_count},
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(503, "Event Service unreachable")
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.json().get("detail", "Reservation failed"))

    # 2) Persist the registration in its own database
    with SessionLocal() as db:
        reg = Registration(**body.model_dump())
        db.add(reg); db.commit(); db.refresh(reg)
        return as_dict(reg)

@app.get("/api/registrations")
def list_registrations():
    with SessionLocal() as db:
        return [as_dict(x) for x in db.query(Registration).all()]