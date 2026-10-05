"""LLM layer: provider pluggable (Anthropic / OpenAI-compatible untuk model open-source / none = rule-based),
validasi JSON, dan groundedness guard yang membuang klaim yang tidak didukung CV."""
import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.ai.prompts import RAG_SYSTEM, SYSTEM_PROMPT, USER_TEMPLATE
from app.core.config import get_settings

log = logging.getLogger(__name__)
LANG = {"id": "Bahasa Indonesia", "en": "English"}


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient:
    def __init__(self) -> None:
        s = get_settings()
        self.provider, self.model = s.llm_provider, s.llm_model
        self.key, self.base, self.timeout = s.llm_api_key, s.llm_base_url.rstrip("/"), s.llm_timeout_s

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> LLMResult:
        try:
            if self.provider == "anthropic":
                r = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": self.model, "max_tokens": max_tokens, "system": system,
                          "messages": [{"role": "user", "content": user}]},
                    timeout=self.timeout,
                )
                r.raise_for_status()
                d = r.json()
                text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
                u = d.get("usage", {})
                return LLMResult(text, u.get("input_tokens", 0), u.get("output_tokens", 0))
            if self.provider == "openai_compatible":
                headers = {"content-type": "application/json"}
                if self.key:
                    headers["authorization"] = f"Bearer {self.key}"
                r = httpx.post(
                    f"{self.base}/chat/completions", headers=headers, timeout=self.timeout,
                    json={"model": self.model, "max_tokens": max_tokens, "temperature": 0.1,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                )
                r.raise_for_status()
                d = r.json()
                u = d.get("usage", {})
                return LLMResult(d["choices"][0]["message"]["content"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise LLMError(f"{type(e).__name__}: {e}") from e
        raise LLMError(f"Provider tidak dikenal: {self.provider}")


def get_llm() -> LLMClient | None:
    s = get_settings()
    if s.llm_provider in ("anthropic", "openai_compatible") and (s.llm_api_key or s.llm_base_url):
        return LLMClient()
    return None


def llm_model_name() -> str:
    s = get_settings()
    return s.llm_model if get_llm() else "rule-based-v1"


# ---------------------------------------------------------------------------
def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").casefold())


def is_grounded(quote: str, cv_norm: str) -> bool:
    q = _norm(re.sub(r"\.{3}|…", " ", quote))
    return len(q) >= 12 and q in cv_norm


def parse_json_object(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise LLMError("Respons LLM bukan JSON.")
    try:
        return json.loads(text[a:b + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON tidak valid: {e}") from e


def _strs(v, limit=10) -> list[str]:
    return [str(x).strip() for x in (v if isinstance(v, list) else []) if str(x).strip()][:limit]


def validate_analysis(raw: dict, cv_text: str, matched: list[str], missing: list[str]) -> tuple[dict, int]:
    """Terapkan skema + groundedness. Mengembalikan (analysis, jumlah_klaim_tidak_didukung)."""
    unsupported = 0
    cv_norm = _norm(cv_text)
    rel = []
    for item in raw.get("relevant_experience") or []:
        if not isinstance(item, dict):
            unsupported += 1
            continue
        ev = str(item.get("evidence") or "").strip()
        if ev and is_grounded(ev, cv_norm):
            rel.append({"requirement": str(item.get("requirement") or "")[:200], "evidence": ev,
                        "explanation": str(item.get("explanation") or "")[:600]})
        else:
            unsupported += 1  # kutipan tidak ada di CV -> halusinasi, dibuang
    allowed = {m.lower() for m in matched}
    unsupported += sum(1 for m in _strs(raw.get("matched_skills"), 50) if m.lower() not in allowed)
    known_missing = {m.lower() for m in missing}
    unsupported += sum(1 for m in _strs(raw.get("missing_skills"), 50) if m.lower() not in known_missing and m.lower() in allowed)
    edu = raw.get("education_match") if isinstance(raw.get("education_match"), dict) else {}
    status = edu.get("status") if edu.get("status") in ("match", "partial", "not_identified") else None
    return {
        # daftar skill = hasil deterministik (otoritatif); LLM hanya boleh menjelaskan
        "matched_skills": matched, "missing_skills": missing,
        "relevant_experience": rel,
        "education_match": {"status": status, "explanation": str(edu.get("explanation") or "")[:400] or None},
        "explanation": str(raw.get("explanation") or "").strip()[:1500] or None,
        "strengths": _strs(raw.get("strengths"), 6),
        "gaps": _strs(raw.get("gaps"), 6),
        "interview_questions": _strs(raw.get("interview_questions"), 8),
    }, unsupported


def llm_analysis(job_title: str, job_text: str, findings: str, cv_text: str, company_context: str,
                 matched: list[str], missing: list[str], language: str = "id") -> tuple[dict, LLMResult, int]:
    client = get_llm()
    if client is None:
        raise LLMError("LLM tidak dikonfigurasi.")
    system = SYSTEM_PROMPT.format(language=LANG.get(language, "Bahasa Indonesia"))
    user = USER_TEMPLATE.format(title=job_title, job_requirements=job_text, findings=findings, cv_text=cv_text,
                                company_context=company_context or "(none)")
    res = client.complete(system, user)
    data, bad = validate_analysis(parse_json_object(res.text), cv_text, matched, missing)
    if not data["explanation"]:
        raise LLMError("Respons LLM tidak memuat penjelasan.")
    return data, res, bad


def llm_answer(question: str, passages: list[str], language: str = "id") -> LLMResult | None:
    client = get_llm()
    if client is None:
        return None
    ctx = "\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages))
    return client.complete(RAG_SYSTEM.format(language=LANG.get(language, "Bahasa Indonesia")),
                           f"<context>\n{ctx}\n</context>\n\nQuestion: {question}", max_tokens=700)
