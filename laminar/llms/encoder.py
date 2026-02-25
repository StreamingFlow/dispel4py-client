import torch
from transformers import AutoModel, AutoTokenizer
import torch.nn.functional as functional
import numpy as np
import json
import io
import base64
import binascii

class LaminarCodeEncoder:

    def __init__(self, text_model_name="sentence-transformers/all-MiniLM-L6-v2",
                 code_model_name="microsoft/codebert-base"):

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.text_tok = AutoTokenizer.from_pretrained(text_model_name)
        self.text_model = AutoModel.from_pretrained(text_model_name)
        self.code_tok = AutoTokenizer.from_pretrained(code_model_name)
        self.code_model = AutoModel.from_pretrained(code_model_name)
        self.text_model.to(self.device).eval()
        self.code_model.to(self.device).eval()

    @torch.no_grad()
    def mean_pool(self, model_out, attn_mask):
        token_emb = model_out.last_hidden_state
        mask = attn_mask.unsqueeze(-1).expand(token_emb.size()).float()
        summed = (token_emb * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        return summed / counts

    @torch.no_grad()
    def embed_text(self, s: str) -> np.ndarray:
        s = (s or "").strip()
        if not s:
            return np.zeros((384,), dtype=np.float32)  # fallback for MiniLM-ish size
        inp = self.text_tok(s, return_tensors="pt", truncation=True, max_length=512, padding=True).to(self.device)
        out = self.text_model(**inp)
        vec = self.mean_pool(out, inp["attention_mask"])
        vec = functional.normalize(vec, p=2, dim=1).squeeze(0).cpu().numpy()
        return vec

    @torch.no_grad()
    def embed_code(self, s: str) -> np.ndarray:

        def maybe_base64_decode(value):
            if isinstance(value, str):
                try:
                    decoded = base64.b64decode(value, validate=True)
                    return decoded
                except (binascii.Error, ValueError):
                    return value
            return value


        s = (s or "").strip()
        if not s:
            return np.zeros((768,), dtype=np.float32)  # CodeBERT hidden size
        s = maybe_base64_decode(s)
        inp = self.code_tok(s, return_tensors="pt", truncation=True, max_length=512, padding=True).to(self.device)
        out = self.code_model(**inp)
        vec = self.mean_pool(out, inp["attention_mask"])
        vec = functional.normalize(vec, p=2, dim=1).squeeze(0).cpu().numpy()
        return vec

    def embed_query(self, query: str, input_type: str):
        desc_embedding = self.embed_text(query) if input_type in ("text", "mixed") else None
        code_embedding = self.embed_code(query) if input_type in ("code", "mixed") else None

        return desc_embedding, code_embedding

    def hybrid_weights(self, input_type: str):
        # return (desc_weight, code_weight)
        if input_type == "mixed":
            return 0.5, 0.5
        if input_type == "code":
            return 0.2, 0.8
        return 1.0, 0.0

    def tag_boost(self, query: str, tags_json: str, max_boost: float = 0.06) -> float:
        if not tags_json:
            return 0.0
        try:
            tags = set(json.loads(tags_json))
        except Exception:
            return 0.0

        q = (query or "").lower()
        hits = 0
        for t in tags:
            t2 = str(t).lower().replace("_", " ")
            if t2 and t2 in q:
                hits += 1

        return min(max_boost, 0.02 * hits)

    def cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        if a is None or b is None or a.size == 0 or b.size == 0:
            return -1.0
        # embeddings already normalized in CELL 3
        return float(np.dot(a, b))

    def from_blob(self, blob: bytes) -> np.ndarray:
        if isinstance(blob, str):
            blob = blob.encode("utf-8")
        buf = io.BytesIO(blob)
        return np.load(buf, allow_pickle=True)