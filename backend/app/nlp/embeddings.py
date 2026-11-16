"""Sentence-Transformer wrapper.

* The model is loaded once (lazily) and shared by all requests.
* Vectors are L2-normalised, so cosine similarity == dot product.
* A small in-process cache avoids re-encoding the same strings (JD
  requirements, skill names) for every resume in a batch.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict

import numpy as np

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_CACHE_SIZE = 20_000

_model = None
_lock = threading.Lock()
_cache: OrderedDict[str, np.ndarray] = OrderedDict()


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(MODEL_NAME, device="cpu")
    return _model


def encode(texts: list[str]) -> np.ndarray:
    """Encode texts -> (n, dim) array of unit vectors."""
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    missing = [t for t in dict.fromkeys(texts) if t not in _cache]
    if missing:
        vecs = get_model().encode(missing, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
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
