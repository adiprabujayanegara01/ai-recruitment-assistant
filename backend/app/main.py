import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.versions import MATCHING_ENGINE_VERSION, PROMPT_VERSION
from app.api import admin, auth, candidates, jobs, knowledge, matching, reports
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import User

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app.request")


def init_db() -> None:
    if settings.environment == "production":
        weak = [n for n, v in (("SECRET_KEY", settings.secret_key), ("JWT_SECRET", settings.jwt_secret)) if v.startswith("change-me") or len(v) < 32]
        if weak or settings.admin_password in ("admin12345",) or len(settings.admin_password) < 12:
            raise RuntimeError(f"Konfigurasi tidak aman untuk production: periksa {', '.join(weak) or 'ADMIN_PASSWORD'} (min 32/12 karakter, bukan default).")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.query(User).filter(User.role == "admin").first():
            db.add(User(name="Administrator", email=settings.admin_email.lower(), password_hash=hash_password(settings.admin_password), role="admin"))
            db.commit()
            log.warning("Admin awal dibuat (%s). Ganti password sebelum production.", settings.admin_email)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name, version="1.0.0", lifespan=lifespan,
    description="Sistem pendukung keputusan screening kandidat: CV/JD parsing, semantic matching, analisis LLM, RAG, dan explainability. "
                "Hasil AI bersifat saran untuk ditinjau manusia.",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = rid
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error rid=%s path=%s", rid, request.url.path)
        return JSONResponse({"detail": "Terjadi kesalahan pada server.", "request_id": rid}, status_code=500, headers={"X-Request-ID": rid})
    ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    log.info("rid=%s %s %s -> %s %.0fms", rid, request.method, request.url.path, response.status_code, ms)
    return response


for r in (auth, candidates, jobs, matching, reports, knowledge, admin):
    app.include_router(r.router, prefix="/api/v1")


@app.get("/health", tags=["system"])
def health():
    from app.services.embedding_service import get_embedder
    from app.services.llm_service import get_llm, llm_model_name

    return {"status": "ok", "embedding_model": get_embedder().name, "llm": llm_model_name() if get_llm() else "rule-based (LLM belum dikonfigurasi)",
            "prompt_version": PROMPT_VERSION, "matching_engine": MATCHING_ENGINE_VERSION}
