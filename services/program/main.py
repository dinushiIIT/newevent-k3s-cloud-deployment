import os
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Program(Base):
    __tablename__ = "programs"
    id = Column(Integer, primary_key=True)
    day = Column(String, nullable=False)           # e.g. "Day 1"
    track = Column(String, nullable=False)         # e.g. "Cloud Computing Track"
    session = Column(String, nullable=False)
    speaker_name = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)

Base.metadata.create_all(engine)

def as_dict(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}

app = FastAPI(title="Program Service",
              docs_url="/api/programs/docs",
              openapi_url="/api/programs/openapi.json")

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

class ProgramIn(BaseModel):
    day: str
    track: str
    session: str
    speaker_name: str
    start_time: str
    end_time: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/programs", status_code=201)
def create_program(body: ProgramIn):
    with SessionLocal() as db:
        p = Program(**body.model_dump())
        db.add(p); db.commit(); db.refresh(p)
        return as_dict(p)

@app.get("/api/programs")
def list_programs(day: str | None = None):
    with SessionLocal() as db:
        q = db.query(Program)
        if day:
            q = q.filter(Program.day == day)
        return [as_dict(p) for p in q.all()]