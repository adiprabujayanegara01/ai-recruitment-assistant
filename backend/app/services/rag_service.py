"""RAG (bagian 9): knowledge base perusahaan -> chunking -> embedding -> retrieval -> jawaban ber-sitasi.
Vektor disimpan sebagai JSON dan dicari dengan numpy (portabel SQLite/PostgreSQL).
Untuk skala besar, ganti VectorStore.search dengan query pgvector (`embedding <=> :q`) tanpa mengubah pemanggil."""
import re

import numpy as np
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.embedding_service import Embedder, cosine_matrix, get_embedder
from app.services.llm_service import llm_answer


def chunk_text(text: str, size: int = 700, overlap: int = 120) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= size:
            cur = f"{cur}\n\n{p}".strip()
            continue
        if cur:
            chunks.append(cur)
        if len(p) <= size:
            cur = p
        else:  # paragraf panjang dipecah per kalimat dengan overlap
            sents, buf = re.split(r"(?<=[.!?])\s+", p), ""
            for s in sents:
                if len(buf) + len(s) + 1 > size and buf:
                    chunks.append(buf)
                    buf = buf[-overlap:] + " " + s
                else:
                    buf = f"{buf} {s}".strip()
            cur = buf
    if cur:
        chunks.append(cur)
    return chunks


def ingest(db: Session, title: str, category: str, text: str, user_id: int | None, emb: Embedder | None = None) -> KnowledgeDocument:
    emb = emb or get_embedder()
    chunks = chunk_text(text)
    vecs = emb.encode([f"{title}. {c}" for c in chunks])  # contextual header: judul dokumen ikut di-embed
    doc = KnowledgeDocument(title=title, category=category, uploaded_by=user_id)
    for i, (c, v) in enumerate(zip(chunks, vecs)):
        doc.chunks.append(KnowledgeChunk(position=i, text=c, embedding=[round(float(x), 5) for x in v], embedding_model=emb.name))
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


class VectorStore:
    def __init__(self, db: Session, emb: Embedder):
        self.db, self.emb = db, emb

    def search(self, query: str, k: int = 4, min_score: float = 0.0) -> list[dict]:
        rows = self.db.query(KnowledgeChunk, KnowledgeDocument.title).join(KnowledgeDocument).filter(
            KnowledgeChunk.embedding_model == self.emb.name).all()  # jangan campur model embedding berbeda
        if not rows:
            return []
        mat = np.asarray([r[0].embedding for r in rows], dtype=np.float32)
        q = self.emb.encode([query])
        sims = cosine_matrix(q, mat)[0]
        order = np.argsort(-sims)[:k]
        return [{"chunk_id": rows[i][0].id, "document_id": rows[i][0].document_id, "title": rows[i][1],
                 "text": rows[i][0].text, "score": round(float(sims[i]), 3)} for i in order if sims[i] >= min_score]


def retrieve(db: Session, query: str, k: int = 3, emb: Embedder | None = None) -> list[dict]:
    emb = emb or get_embedder()
    return VectorStore(db, emb).search(query, k=k, min_score=emb.related_threshold * 0.7)


def ask(db: Session, question: str, language: str = "id", k: int = 4) -> dict:
    emb = get_embedder()
    hits = retrieve(db, question, k=k, emb=emb)
    if not hits:
        return {"answer": None, "found": False, "sources": [], "mode": "none"}
    res = llm_answer(question, [h["text"] for h in hits], language)
    if res is not None:
        if res.text.strip() == "NOT_FOUND":
            return {"answer": None, "found": False, "sources": hits, "mode": "llm"}
        return {"answer": res.text.strip(), "found": True, "sources": hits, "mode": "llm"}
    # tanpa LLM: jawaban ekstraktif = 2 kalimat paling relevan dari potongan yang ditemukan, tetap ber-sumber
    sents = [x.strip() for h in hits for x in re.split(r"(?<=[.!?])\s+|\n+", h["text"]) if len(x.strip()) > 25 and not x.startswith("#")]
    if sents:
        sims = cosine_matrix(emb.encode([question]), emb.encode(sents))[0]
        top = sorted(np.argsort(-sims)[:2])
        return {"answer": " ".join(sents[i] for i in top), "found": True, "sources": hits, "mode": "extractive"}
    return {"answer": hits[0]["text"], "found": True, "sources": hits, "mode": "extractive"}
