"""Embedding service.

Dua backend dengan antarmuka sama:
- SentenceTransformerEmbedder : model semantic sungguhan (default multilingual, mendukung Bahasa Indonesia).
- HashingEmbedder             : fallback offline & deterministik (tanpa unduhan model) untuk dev/test/CI.
                                Memakai n-gram + fitur kanonik dari taxonomy skill.
Keduanya menghasilkan vektor ter-normalisasi sehingga cosine similarity = dot product."""
import logging
import re
import zlib
from functools import lru_cache

import numpy as np

from app.core.config import get_settings
from app.services.skills import get_taxonomy, implied

log = logging.getLogger(__name__)

_STOP = set(
    "the a an and or of to in on for with by at from as is are be been was were this that these those it its into "
    "using use used build built developed develop work working experience years year strong skills skill ability "
    "yang dan atau di ke dari untuk dengan pada dalam oleh sebagai adalah ini itu serta juga memakai menggunakan "
    "pengalaman kemampuan membangun mengembangkan".split()
)


class Embedder:
    name: str = "base"
    dim: int = 0
    matched_threshold: float = 0.6
    related_threshold: float = 0.45

    def encode(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    matched_threshold = 0.60
    related_threshold = 0.45

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.name = f"st:{model_name}"
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.asarray(self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)


class HashingEmbedder(Embedder):
    name = "hashing-v1"
    dim = 1024
    matched_threshold = 0.42
    related_threshold = 0.28

    def _feat(self, vec: np.ndarray, token: str, weight: float) -> None:
        h = zlib.crc32(token.encode())
        vec[h % self.dim] += weight if (h >> 16) & 1 else -weight

    def _encode_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tax = get_taxonomy()
        for canon in tax.find(text):  # fitur konsep: "ML" dan "machine learning" bertemu di sini
            self._feat(vec, "§" + canon.lower(), 2.0)
            for imp in implied(canon):
                self._feat(vec, "§" + imp.lower(), 1.2)
        words = [w for w in re.findall(r"[a-zA-Z0-9+#.]+", text.lower()) if w not in _STOP and len(w) > 1]
        for w in words:
            self._feat(vec, "w:" + w, 1.0)
            padded = f"<{w}>"
            for n in (3, 4):
                for i in range(len(padded) - n + 1):
                    self._feat(vec, f"c{n}:{padded[i:i + n]}", 0.25)
        for a, b in zip(words, words[1:]):
            self._feat(vec, f"b:{a}_{b}", 0.6)
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack([self._encode_one(t) for t in texts])


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_backend in ("auto", "sentence-transformers"):
        try:
            return SentenceTransformerEmbedder(s.embedding_model)
        except Exception as e:  # ImportError / gagal unduh model
            if s.embedding_backend == "sentence-transformers":
                raise
            log.warning("sentence-transformers tidak tersedia (%s). Memakai HashingEmbedder.", e)
    return HashingEmbedder()


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a: (n,d), b: (m,d) ter-normalisasi -> (n,m)."""
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float32)
    return a @ b.T
