from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import onnxruntime as ort

#session = ort.InferenceSession("model.onnx", providers=["CPUExecutionProvider"])

class InPayload(BaseModel):
    text: str

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/predict")
def predict(payload: InPayload):
    text = payload.text or ""

    result = len(text.strip()) % 2 == 0
    return {"result": result}
