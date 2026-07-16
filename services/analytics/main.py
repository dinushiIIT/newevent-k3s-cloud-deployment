import os, json, httpx
from fastapi import FastAPI, Request, Response

CH_URL = os.environ.get("CLICKHOUSE_URL", "http://clickhouse:8123")
CH_USER = os.environ.get("CLICKHOUSE_USER", "analytics")
CH_PASS = os.environ["CLICKHOUSE_PASSWORD"]

ALLOWED = {"event_type", "session_id", "page", "section", "label",
           "referrer", "device", "viewport_w", "duration_ms"}

client = httpx.AsyncClient(timeout=3.0)

app = FastAPI(title="Analytics Service",
              docs_url="/api/analytics/docs",
              openapi_url="/api/analytics/openapi.json")

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/analytics/collect", status_code=204)
async def collect(req: Request):
    try:
        raw = await req.json()
    except Exception:
        return Response(status_code=400)
    row = {k: v for k, v in raw.items() if k in ALLOWED}
    if "event_type" not in row:
        return Response(status_code=400)
    try:
        await client.post(
            f"{CH_URL}/",
            params={
                "query": "INSERT INTO analytics.events FORMAT JSONEachRow",
                "async_insert": "1",
                "wait_for_async_insert": "0",
            },
            content=json.dumps(row),
            auth=(CH_USER, CH_PASS),
        )
    except Exception as e:
        print(f"ClickHouse insert failed: {e}")
    return Response(status_code=204)