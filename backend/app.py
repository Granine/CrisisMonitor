# backend/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import httpx
from pymongo import MongoClient
from datetime import datetime, timezone

MODEL_URL = f"http://{os.getenv('MODEL_SERVICE_HOST','model-svc')}:{os.getenv('MODEL_SERVICE_PORT','8000')}"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:example@mongodb-0.mongodb-svc.mlapp.svc.cluster.local:27017/?authSource=admin")
DB_NAME = os.getenv("MONGO_DB", "mlapp")

app = FastAPI()

#test

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
events = db["events"]

class InPayload(BaseModel):
    text: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/classify")
async def classify(payload: InPayload):
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            r = await client.post(f"{MODEL_URL}/predict", json={"text": payload.text})
            r.raise_for_status()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Model service error: {e}")

    data = r.json()
    result = bool(data.get("result"))
    events.insert_one({
        "text": payload.text,
        "result": result,
        "ts": datetime.now(timezone.utc),
    })
    return {"result": result}
