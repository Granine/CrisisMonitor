import os, re, json, pathlib, numpy as np, torch, wandb
from abc import ABC, abstractmethod
import onnxruntime as ort
from transformers import AutoTokenizer, AutoModelForSequenceClassification
    

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class TextModel(ABC):
    @abstractmethod
    def predict_one(self, text: str, max_len: int):
        pass

# Light tweet normalization (same as training)
def normalize_tweet(t: str) -> str:
    URL_RE  = re.compile(r"https?://\S+|www\.\S+")
    USER_RE = re.compile(r"@\w+")
    t = URL_RE.sub(" <url> ", str(t))
    t = USER_RE.sub(" <user> ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

class ORTModel(TextModel):
    def __init__(self, ort_session: ort.InferenceSession, tokenizer, IDX2LABEL: dict):
        super().__init__()
        self.ort_sesion = ort_session
        self.tokenizer = tokenizer
        self.IDX2LABEL = IDX2LABEL

    @torch.inference_mode()
    def predict_one(self, text: str, max_len: int = 256):
        text = normalize_tweet(text)
        enc = self.tokenizer([text], max_length=max_len, truncation=True, padding=True, return_tensors="np")
        sess_input_names = [i.name for i in self.ort_sesion.get_inputs()]

        # --- feed ONLY what the graph declares; synthesize token_type_ids if required ---
        feed = {}
        for name in sess_input_names:
            if name in enc:
                feed[name] = enc[name].astype(np.int64)
            elif name == "token_type_ids":
                feed[name] = np.zeros_like(enc["input_ids"], dtype=np.int64)
            else:
                # If the graph expects a name we didn't create, fail loudly
                raise KeyError(f"Missing required ONNX input: {name}")

        logits = self.ort_sesion.run(["logits"], feed)[0]
        probs = torch.softmax(torch.tensor(logits), dim=-1).numpy()[0]
        pred = int(np.argmax(probs))
        return self.IDX2LABEL.get(pred, pred), f"P({self.IDX2LABEL.get(0,'0')})={probs[0]:.3f}, P({self.IDX2LABEL.get(1,'1')})={probs[1]:.3f}"
    
class HFModel(TextModel):
    def __init__(self, model: AutoModelForSequenceClassification, tokenizer: AutoTokenizer, IDX2LABEL: dict):
        super().__init__()
        self.model = model
        self.tokenizer = tokenizer
        self.IDX2LABEL = IDX2LABEL

    @torch.inference_mode()
    def predict_one(self, text: str, max_len: int = 256):
        text = normalize_tweet(text)
        enc = self.tokenizer(text, truncation=True, max_length=max_len, padding=True, return_tensors="pt")
        enc = {k: v.to(device) for k, v in enc.items()}
        logits = self.model(**enc).logits
        probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()
        pred = int(np.argmax(probs))
        return self.IDX2LABEL.get(pred, pred), f"P({self.IDX2LABEL.get(0,'0')})={probs[0]:.3f}, P({self.IDX2LABEL.get(1,'1')})={probs[1]:.3f}"

def start() -> TextModel:
    ENTITY = "alice-chua-university-of-toronto-org"  # org/user that owns the registry
    TARGET = "wandb-registry-model/disaster-tweet-model-registry"  # collection (no entity here)
    ALIAS  = "production"

    api = wandb.Api()
    art = api.artifact(f"{ENTITY}/{TARGET}:{ALIAS}")
    local_dir = art.download()
    meta = art.metadata or {}
    fmt  = (meta.get("format") or "").lower()
    print("Downloaded artifact:", art.name, "| type:", getattr(art, "type", "?"), "| format:", fmt)
    print("Local dir:", local_dir)


    # ----- helpers -----
    def _find_one(root: str, pattern: str) -> str:
        p = list(pathlib.Path(root).rglob(pattern))
        return str(p[0]) if p else ""

    def resolve_model_name(local_dir: str, meta: dict) -> str:
        # 1) prefer explicit metadata from training/logging
        if meta and meta.get("model_id"):
            return meta["model_id"]
        # 2) try HF config if present (PyTorch export)
        cfg_path = os.path.join(local_dir, "config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                # HF usually stores the original model id here
                if "_name_or_path" in cfg and cfg["_name_or_path"]:
                    return cfg["_name_or_path"]
                # fall back to model_type if name_or_path missing
                if "model_type" in cfg:
                    return cfg["model_type"]
            except Exception:
                pass
        # 3) ONNX-only: look for a hint file we saved
        hint = os.path.join(local_dir, "tokenizer", "special_tokens_map.json")
        if os.path.exists(hint):
            try:
                tok = AutoTokenizer.from_pretrained(os.path.dirname(hint), use_fast=True)
                if getattr(tok, "name_or_path", None):
                    return tok.name_or_path
            except Exception:
                pass
        # 4) last resort: artifact name or folder basename
        return getattr(art, "name", os.path.basename(local_dir))

    MODEL_NAME = resolve_model_name(local_dir, meta)
    print("Resolved model name:", MODEL_NAME)
        
    # Label mapping (fallback if not present in config)
    DEFAULT_ID2LABEL = {0: "not disaster", 1: "disaster"}
    
    IDX2LABEL = DEFAULT_ID2LABEL
    
    # ===== Branch A: ONNX artifact =====
    onnx_path = _find_one(local_dir, "*.onnx")
    if fmt == "onnx" or onnx_path:

    
        tok_dir = _find_one(local_dir, "tokenizer") or local_dir
        tokenizer = AutoTokenizer.from_pretrained(tok_dir, use_fast=True)
    
        # try to load id2label if present
        id2label_path = _find_one(local_dir, "id2label.json")
        if id2label_path:
            with open(id2label_path, "r") as f:
                raw = json.load(f)
            IDX2LABEL = {int(k): v for k, v in raw.items()}
    
        sess = ort.InferenceSession(onnx_path or _find_one(local_dir, "*.onnx"), providers=["CPUExecutionProvider"])
        print("Loaded ONNX @production ✅ | model:", MODEL_NAME)
        return ORTModel(sess, tokenizer, IDX2LABEL)

    # ===== Branch B: PyTorch HF directory =====
    else:

        tokenizer = AutoTokenizer.from_pretrained(local_dir, use_fast=True)
        model = AutoModelForSequenceClassification.from_pretrained(local_dir)
        if getattr(model.config, "id2label", None):
            IDX2LABEL = {int(k): v for k, v in model.config.id2label.items()}
        
        model.to(device).eval()

        print("Loaded PyTorch HF @production ✅ | model:", MODEL_NAME)
        return HFModel(model, tokenizer, IDX2LABEL)