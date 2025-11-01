from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, time, tempfile, json, math
import requests
import onnxruntime as ort
import numpy as np

from transformers import AutoTokenizer

class InPayload(BaseModel):
    text: str

app = FastAPI()

# Globals for readiness
SESSION = None
READY = False
ERROR = None

def download_model(url: str, dst_path: str):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dst_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

def build_inputs(tokenizer, text: str, session: ort.InferenceSession):
    # Tokenize to NumPy for ONNX Runtime
    enc = tokenizer(
        text,
        return_tensors="np",
        truncation=True,
        padding="max_length",
        max_length=128,
    )
    # Map tokenizer outputs to ONNX input names (commonly: input_ids, attention_mask)
    feed = {}
    sess_inputs = [i.name for i in session.get_inputs()]
    for k, v in enc.items():
        if k in sess_inputs:
            feed[k] = v
    # Some models expect token_type_ids even if all zeros
    if "token_type_ids" in sess_inputs and "token_type_ids" not in feed:
        feed["token_type_ids"] = np.zeros_like(enc["input_ids"])
    return feed

def postprocess(outputs):
    # Assume a classifier with logits [1, num_labels]
    # Interpret label 1 as "True"
    logits = None
    if isinstance(outputs, list):
        logits = outputs[0]
    elif isinstance(outputs, dict):
        # If model returns named outputs
        logits = list(outputs.values())[0]
    else:
        raise RuntimeError("Unexpected ONNX outputs")

    # Softmax & argmax
    probs = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probs = probs / probs.sum(axis=-1, keepdims=True)
    pred = int(np.argmax(probs, axis=-1).item())
    result = bool(pred == 1) if probs.shape[-1] >= 2 else bool(pred)
    return result, probs.tolist()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    if READY:
        return {"ready": True}
    if ERROR:
        return JSONResponse(status_code=500, content={"ready": False, "error": str(ERROR)})
    return JSONResponse(status_code=503, content={"ready": False})

@app.post("/predict")
def predict(payload: InPayload):
    if not READY or SESSION is None:
        return JSONResponse(status_code=503, content={"detail": "Model not ready"})
    text = payload.text or ""
    feed = build_inputs(app.state.tokenizer, text, SESSION)
    outputs = SESSION.run(None, feed)
    result, _ = postprocess(outputs)
    return {"result": result}

def _load_on_start():
    global SESSION, READY, ERROR
    try:
        onnx_url = os.environ.get("ONNX_URL")
        tokenizer_id = os.environ.get("TOKENIZER_ID", "distilbert-base-uncased")
        if not onnx_url:
            raise RuntimeError("ONNX_URL not provided")

        os.makedirs("/models", exist_ok=True)
        model_path = "/models/model.onnx"
        # Download only if not present
        if not os.path.exists(model_path):
            download_model(onnx_url, model_path)

        # Create session
        providers = ort.get_available_providers()
        SESSION = ort.InferenceSession(model_path, providers=providers)

        # Tokenizer (downloads vocab once; cached in /root/.cache/huggingface by default)
        app.state.tokenizer = AutoTokenizer.from_pretrained(tokenizer_id)

        READY = True
    except Exception as e:
        ERROR = e
        READY = False

# Load asynchronously after startup so container can come up quickly
@app.on_event("startup")
def _startup():
    _load_on_start()
