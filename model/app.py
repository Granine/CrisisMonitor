from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, json, tempfile, requests, onnxruntime as ort
import numpy as np
from transformers import AutoTokenizer
import onnx
import os, re, json, pathlib, numpy as np, torch, wandb
from services import start, TextModel

class InPayload(BaseModel):
    text: str

app = FastAPI()

SESSION: TextModel | None = None
READY = False
ERROR = None

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    if SESSION:
        return {"ready": True}
    if ERROR:
        return JSONResponse(status_code=500, content={"ready": False, "error": str(ERROR)})
    return JSONResponse(status_code=503, content={"ready": False})

@app.post("/predict")
def predict(payload: InPayload):
    if SESSION == None:
        return { "status": "not ready" }
    pred, probs = SESSION.predict_one(payload.text, 256)
    return {"pred": str(pred), "probs": str(probs) }

@app.on_event("startup")
def _startup():
    global SESSION
    try:
        SESSION = start()
    except Exception as ex:
        ERROR = ex
