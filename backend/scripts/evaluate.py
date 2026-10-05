"""Evaluation harness (bagian 15). Jalankan:  python -m scripts.evaluate  (dari folder backend/)

Mengukur: extraction (P/R/F1), ranking (Precision@K, Recall@K, NDCG@K), groundedness evidence,
counterfactual fairness, dan latency. Hasil dibandingkan antar versi model/prompt lewat data/eval/results.json."""
import json
import math
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os  # noqa: E402

os.environ.setdefault("EMBEDDING_BACKEND", "hashing")

from app.ai.versions import MATCHING_ENGINE_VERSION, PROMPT_VERSION  # noqa: E402
from app.services.cv_parser import parse_cv  # noqa: E402
from app.services.embedding_service import get_embedder  # noqa: E402
from app.services.jd_parser import parse_jd  # noqa: E402
from app.services.matching_service import analyze_match  # noqa: E402
from app.services.skills import get_taxonomy  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "data"
TODAY = date(2026, 9, 30)  # tetap, agar hasil reproducible


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.casefold())


def prf(pred: set, gold: set) -> tuple[float, float, float]:
    tp = len(pred & gold)
    p, r = tp / len(pred) if pred else 0.0, tp / len(gold) if gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def ndcg(ranked: list[str], rel: dict[str, int], k: int) -> float:
    dcg = sum((2 ** rel.get(c, 0) - 1) / math.log2(i + 2) for i, c in enumerate(ranked[:k]))
    ideal = sorted(rel.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def main() -> dict:
    gold = json.loads((DATA / "eval" / "gold.json").read_text(encoding="utf-8"))
    emb, tax = get_embedder(), get_taxonomy()
    texts = {k: (DATA / "sample_cvs" / f"{k}.txt").read_text(encoding="utf-8") for k in gold["cvs"]}
    cvs = {k: parse_cv(t, today=TODAY) for k, t in texts.items()}
    jds = {k: parse_jd(v["title"], (DATA / "sample_jobs" / f"{k}.txt").read_text(encoding="utf-8")) for k, v in gold["jobs"].items()}

    # ---- Extraction ----
    tp = fp = fn = 0
    name_ok = email_ok = edu_ok = ent_ok = 0
    year_err = []
    misses = {}
    for k, g in gold["cvs"].items():
        pred = {s for s in cvs[k]["skills"] if tax.canonical(s)}
        gs = set(g["skills"])
        tp, fp, fn = tp + len(pred & gs), fp + len(pred - gs), fn + len(gs - pred)
        if pred != gs:
            misses[k] = {"false_positive": sorted(pred - gs), "false_negative": sorted(gs - pred)}
        c = cvs[k]
        name_ok += c["personal"]["name"] == g["name"]
        email_ok += c["personal"]["email"] == g["email"]
        edu_ok += c["highest_education_level"] == g["education_level"]
        ent_ok += len(c["experience"]) == g["experience_entries"]
        year_err.append(abs(c["total_experience_years"] - g["total_years"]))
    n = len(gold["cvs"])
    p, r = tp / (tp + fp), tp / (tp + fn)
    extraction = {"skills_precision": round(p, 3), "skills_recall": round(r, 3), "skills_f1": round(2 * p * r / (p + r), 3),
                  "name_accuracy": name_ok / n, "email_accuracy": email_ok / n, "education_level_accuracy": edu_ok / n,
                  "experience_entries_accuracy": ent_ok / n, "total_years_mae": round(statistics.mean(year_err), 2), "skill_errors": misses}

    # ---- Ranking + groundedness + latency ----
    ranking, times, grounded, total_ev = {}, [], 0, 0
    results = {}
    for j, jd in jds.items():
        rel = gold["jobs"][j]["relevance"]
        scored = []
        for k in cvs:
            t0 = time.perf_counter()
            out = analyze_match(cvs[k], jd, emb, cvs[k]["personal"]["name"])
            times.append((time.perf_counter() - t0) * 1000)
            scored.append((k, out["match_score"]))
            results[(k, j)] = out["match_score"]
            for d in out["details"]:
                if d["evidence"] and d["evidence_section"] != "skills":
                    total_ev += 1
                    grounded += norm(d["evidence"]) in norm(texts[k]) or d["method"] == "implied" and norm(d["evidence"]) in norm(texts[k])
        ranked = [k for k, _ in sorted(scored, key=lambda x: -x[1])]
        strong = {c for c, g in rel.items() if g >= 2}
        ranking[j] = {"ranked": [f"{k} ({dict(scored)[k]})" for k in ranked],
                      "P@1": float(ranked[0] in strong), "P@2": len(set(ranked[:2]) & strong) / 2,
                      "recall@2": len(set(ranked[:2]) & strong) / len(strong), "NDCG@5": round(ndcg(ranked, rel, 5), 3)}

    # ---- Counterfactual fairness ----
    swaps = [("Laki-laki", "Perempuan"), ("Islam", "Kristen"), ("Menikah", "Belum menikah")]
    max_delta = 0.0
    for k, t in texts.items():
        for a, b in swaps:
            t2 = t.replace(a, b).replace(gold["cvs"][k]["name"], "Nama Lain")
            c2 = parse_cv(t2, today=TODAY)
            for j, jd in jds.items():
                max_delta = max(max_delta, abs(analyze_match(c2, jd, emb, c2["personal"]["name"])["match_score"] - results[(k, j)]))

    report = {
        "versions": {"embedding": emb.name, "matching_engine": MATCHING_ENGINE_VERSION, "prompt": PROMPT_VERSION},
        "n_cvs": n, "n_jobs": len(jds), "extraction": extraction, "ranking": ranking,
        "mean_ranking": {m: round(statistics.mean(v[m] for v in ranking.values()), 3) for m in ("P@1", "P@2", "recall@2", "NDCG@5")},
        "groundedness": {"evidence_verbatim_rate": round(grounded / total_ev, 3) if total_ev else None, "evidence_items": total_ev},
        "fairness": {"max_score_delta_under_sensitive_attribute_swap": round(max_delta, 3)},
        "latency_ms": {"mean_per_match": round(statistics.mean(times), 1), "p95": round(sorted(times)[int(len(times) * 0.95) - 1], 1)},
    }
    out = DATA / "eval" / "results.json"
    hist = json.loads(out.read_text()) if out.exists() else []
    hist = [h for h in hist if h["versions"] != report["versions"]] + [report]
    out.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, ensure_ascii=False))
