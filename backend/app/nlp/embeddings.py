"""Sentence embeddings for semantic matching.

Model: sentence-transformers/all-MiniLM-L6-v2 (384-d), the same weights either way.
Two interchangeable engines run it:

  * "onnx"  (default) ONNX Runtime on the model's official ONNX export.
            ~150 MB of memory instead of ~1 GB, so the app fits small hosts.
  * "torch" the sentence-transformers library on PyTorch (optional extra:
            `uv sync --extra torch`), kept for verification.

The ONNX path reproduces sentence-transformers exactly: same tokenizer,
truncation at 256 tokens, mean pooling over the attention mask, L2
normalisation. scripts/compare_engines.py checks that both engines give the
same vectors and the same candidate scores.

Shared behaviour:
  * the model is loaded once (lazily) and shared by all requests;
  * vectors are unit length, so cosine similarity == dot product;
  * an in-process cache avoids re-encoding the same strings (JD requirements,
    skill descriptions) for every resume in a batch.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict

import numpy as np

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
ENGINE = os.getenv("EMBEDDING_ENGINE", "onnx").lower()
MAX_TOKENS = 256
DIM = 384
_CACHE_SIZE = 20_000
_BATCH = 32

_model = None
_lock = threading.Lock()
_cache: OrderedDict[str, np.ndarray] = OrderedDict()


class OnnxEncoder:
    """all-MiniLM-L6-v2 on ONNX Runtime, matching sentence-transformers' output."""

    def __init__(self, model_name: str):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(hf_hub_download(model_name, "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAX_TOKENS)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
        self.session = ort.InferenceSession(hf_hub_download(model_name, "onnx/model.onnx"), opts,
                                            providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}

    def encode(self, texts: list[str]) -> np.ndarray:
        out = []
        for start in range(0, len(texts), _BATCH):
            batch = self.tokenizer.encode_batch(texts[start:start + _BATCH])
            ids = np.array([e.ids for e in batch], dtype=np.int64)
            mask = np.array([e.attention_mask for e in batch], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.input_names:
                feed["token_type_ids"] = np.zeros_like(ids)
            tokens = self.session.run(None, feed)[0]
            m = mask[..., None].astype(np.float32)
            pooled = (tokens * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            out.append(pooled / np.clip(norms, 1e-12, None))
        return np.vstack(out).astype(np.float32)


class TorchEncoder:
    """Reference implementation via sentence-transformers (requires the 'torch' extra)."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device="cpu")

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, batch_size=64, normalize_embeddings=True,
                                 show_progress_bar=False).astype(np.float32)


def make_encoder(engine: str = ENGINE, model_name: str = MODEL_NAME):
    if engine == "torch":
        return TorchEncoder(model_name)
    if engine == "onnx":
        return OnnxEncoder(model_name)
    raise ValueError(f"Unknown EMBEDDING_ENGINE {engine!r} (use 'onnx' or 'torch')")


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = make_encoder()
    return _model


def encode(texts: list[str]) -> np.ndarray:
    """Encode texts -> (n, 384) array of unit vectors."""
    if not texts:
        return np.zeros((0, DIM), dtype=np.float32)
    missing = [t for t in dict.fromkeys(texts) if t not in _cache]
    if missing:
        vecs = get_model().encode(missing)
        with _lock:
            for t, v in zip(missing, vecs):
                _cache[t] = v
                if len(_cache) > _CACHE_SIZE:
                    _cache.popitem(last=False)
    return np.vstack([_cache[t] for t in texts])


def cosine_matrix(a: list[str], b: list[str]) -> np.ndarray:
    """Pairwise cosine similarity between two lists of strings: shape (len(a), len(b))."""
    if not a or not b:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    return encode(a) @ encode(b).T
