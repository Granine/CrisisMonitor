from fastapi import FastAPI
from .dto import TweetInput, PredictionOutput
from fastapi.middleware.cors import CORSMiddleware
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


# Define allowed origins (frontend domains)
origins = [
    "http://localhost:3000",     # local dev (React/Vite/Next.js)
    "https://disaster-classification-mscac.netlify.app/",  # deployed frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # List of allowed origins
    allow_credentials=True,
    allow_methods=["*"],              # Allow all HTTP methods
    allow_headers=["*"],              # Allow all headers
)

@app.get("/")
def home():
    return {"message": "Hello FastAPI"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict-tweet")
async def classify(payload: TweetInput):
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
    return PredictionOutput(is_real_disaster=result)
