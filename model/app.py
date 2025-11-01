from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, json, tempfile, requests, onnxruntime as ort
import numpy as np
from transformers import AutoTokenizer
import onnx

class InPayload(BaseModel):
    text: str

app = FastAPI()

SESSION = None
READY = False
ERROR = None
# tttttt

def download_model(url: str, dst_path: str):
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dst_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

def extract_model_metadata(onnx_path: str):
    """Try to read the original model id from ONNX metadata."""
    try:
        model = onnx.load(onnx_path)
        meta = {p.key: p.value for p in model.metadata_props}
        # Common keys:
        #   "model_type": "distilbert"
        #   "hf_pretrained_model_name_or_path": "distilbert-base-uncased"
        model_id = meta.get("hf_pretrained_model_name_or_path") or meta.get("model_type")
        return model_id
    except Exception as e:
        print(f"⚠️ Could not read ONNX metadata: {e}")
        return None

def build_inputs(tokenizer, text: str, session: ort.InferenceSession):
    enc = tokenizer(
        text,
        return_tensors="np",
        truncation=True,
        padding="max_length",
        max_length=128,
    )
    feed = {}
    sess_inputs = [i.name for i in session.get_inputs()]
    for k, v in enc.items():
        if k in sess_inputs:
            feed[k] = v
    if "token_type_ids" in sess_inputs and "token_type_ids" not in feed:
        feed["token_type_ids"] = np.zeros_like(enc["input_ids"])
    return feed

def postprocess(outputs):
    logits = outputs[0] if isinstance(outputs, list) else list(outputs.values())[0]
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
        if not onnx_url:
            raise RuntimeError("ONNX_URL not provided")

        os.makedirs("/models", exist_ok=True)
        model_path = "/models/model.onnx"

        if not os.path.exists(model_path):
            print(f"📥 Downloading model from {onnx_url}")
            download_model(onnx_url, model_path)
            print("✅ Model downloaded")

        providers = ort.get_available_providers()
        SESSION = ort.InferenceSession(model_path, providers=providers)

        # --- 🔍 Auto-detect tokenizer from ONNX metadata
        model_id = extract_model_metadata(model_path)
        if not model_id:
            print("⚠️ No model id found in metadata, defaulting to 'distilbert-base-uncased'")
            model_id = "distilbert-base-uncased"

        print(f"🧩 Loading tokenizer: {model_id}")
        app.state.tokenizer = AutoTokenizer.from_pretrained(model_id)

        READY = True
        print("✅ Model and tokenizer ready")
    except Exception as e:
        ERROR = e
        READY = False
        print(f"❌ Model load failed: {e}")

@app.on_event("startup")
def _startup():
    _load_on_start()
