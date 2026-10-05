# AI Recruitment Assistant

> **Explainable & Fair AI-Assisted Candidate Screening**

AI Recruitment Assistant is an AI-powered **decision-support system for recruitment** that helps recruiters analyze CVs against Job Descriptions using deterministic scoring, semantic matching, evidence-based analysis, optional LLM assistance, and RAG.

The system is designed around a **human-in-the-loop** principle: AI provides analysis and evidence, while the final recruitment decision remains with a human recruiter.

**NLP · Semantic Matching · LLM · RAG · Explainable AI · Fairness · FastAPI · React · PostgreSQL · Docker**

---

## ✨ Key Features

- 📄 **CV Parsing** — Extract information from PDF and DOCX resumes.
- 🎯 **Job Description Parsing** — Extract skills, requirements, education, experience, and responsibilities.
- 🧠 **Semantic Matching** — Compare candidate profiles with job requirements.
- 📊 **Explainable Scoring** — Show score components and the evidence behind each assessment.
- 🔎 **Evidence-Based Analysis** — Candidate claims must be supported by information extracted from the CV.
- 🤖 **Optional LLM Analysis** — Supports Anthropic and OpenAI-compatible providers.
- 📚 **RAG Knowledge Base** — Retrieve company knowledge and provide cited answers.
- 🛡️ **Prompt Injection Protection** — Treat CV content as untrusted input.
- ⚖️ **Fairness by Design** — Redacts sensitive attributes before AI analysis.
- 🔐 **Authentication & Authorization** — JWT-based authentication with Admin and Recruiter roles.
- 📝 **Audit Trail** — Record important recruitment system activities.
- 🗑️ **Data Retention** — Support controlled deletion of stored candidate data.
- 📈 **Batch Analysis & Ranking** — Analyze multiple candidates against a job.
- 📑 **PDF Reports** — Generate analysis reports.
- 🐳 **Docker Support** — Run the application with PostgreSQL and pgvector.
- 📴 **Offline Mode** — The system can operate without an external LLM.

---

## 🏗️ Architecture

```text
┌──────────────────────┐
│   React Dashboard    │
└──────────┬───────────┘
           │ REST API
           ▼
┌──────────────────────┐
│      FastAPI         │
│ Authentication/API   │
└──────────┬───────────┘
           │
     ┌─────┴───────────────┐
     │                     │
     ▼                     ▼
┌─────────────┐      ┌───────────────┐
│ CV/JD Parser│      │ Knowledge Base│
└──────┬──────┘      └───────┬───────┘
       │                      │
       ▼                      ▼
┌─────────────────────────────────────┐
│       Matching & Analysis Engine    │
│  Rule-based + Embedding + Evidence │
└──────────────────┬──────────────────┘
                   │
          ┌────────┴─────────┐
          ▼                  ▼
     Optional LLM        Audit / Logs
          │
          ▼
    Explainable Result
```

---

## 🧮 Scoring Model

The default scoring model is:

```text
Score =
    Skill       × 40%
  + Experience  × 30%
  + Education   × 15%
  + Project     × 15%
```

The weights are configurable and should be validated against an appropriate evaluation dataset before being used in real recruitment.

### Important Design Principle

**The LLM does not determine the candidate's primary score.**

The main score is calculated by the deterministic matching engine. The LLM is used as an optional explanation and analysis layer.

This helps reduce the risk of:

- hallucinated scores
- arbitrary model decisions
- unsupported candidate claims
- inconsistent scoring

---

## 🔍 Evidence-Based Analysis

For every requirement, the system attempts to identify supporting evidence from the candidate's CV.

Evidence can be classified as:

- Direct mention
- Declared skill
- Implicit evidence
- Related/equivalent skill
- Semantic similarity
- Not identified

If sufficient evidence cannot be found, the system should report that the requirement is **not identified** rather than inventing evidence.

---

## ⚖️ Fairness & Privacy

The system is designed to reduce the influence of sensitive candidate attributes during AI analysis.

Sensitive information such as:

- gender
- religion
- age
- marital status
- nationality
- ethnicity
- phone number
- email
- personal URLs
- candidate name

is redacted before relevant AI processing.

The project also includes counterfactual and prompt-injection tests.

### Important

Fairness safeguards do **not** guarantee that the system is bias-free.

Real-world recruitment data should be evaluated for:

- demographic bias
- false positives
- false negatives
- disparate impact
- proxy variables
- domain-specific bias
- model drift

---

## 🛡️ Security

The application includes several security controls:

- Environment-based secrets
- Password hashing using `scrypt`
- JWT authentication
- Role-based authorization
- Upload size validation
- File extension validation
- PDF/DOCX magic-byte validation
- Randomized stored filenames
- Audit logging
- Candidate access restrictions
- Data retention controls
- Prompt injection detection
- PII redaction
- Production configuration checks

### Before Production

The following are strongly recommended:

1. Generate strong random secrets.
2. Never use default credentials.
3. Configure HTTPS.
4. Use secure secret management.
5. Enable rate limiting for authentication endpoints.
6. Encrypt backups and storage where appropriate.
7. Review access controls.
8. Run security testing.
9. Run bias/fairness evaluation on representative data.
10. Add database migrations.
11. Review dependency vulnerabilities.
12. Enable GitHub security features.

---

## 🚀 Quick Start

### Option A — Local Development

#### 1. Clone the repository

```bash
git clone https://github.com/adiprabujayanegara01/ai-recruitment-assistant.git
cd ai-recruitment-assistant
```

#### 2. Create Python environment

```bash
cd backend

python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

#### 3. Install dependencies

```bash
pip install -r requirements-dev.txt
```

#### 4. Start demo data

```bash
python -m scripts.seed
```

#### 5. Start backend

```bash
uvicorn app.main:app --reload
```

API:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

#### 6. Start frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Dashboard:

```text
http://localhost:5173
```

---

## 🐳 Docker

Create your local environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Fill the required secrets in `.env`.

Then:

```bash
docker compose up --build
```

Frontend:

```text
http://localhost:3000
```

API:

```text
http://localhost:8000/docs
```

---

## 🤖 LLM Configuration

The application can operate without an external LLM.

### Offline / Rule-Based

```env
LLM_PROVIDER=none
```

### Anthropic

```env
LLM_PROVIDER=anthropic
LLM_API_KEY=YOUR_API_KEY
LLM_MODEL=YOUR_MODEL
```

### OpenAI-Compatible Provider

```env
LLM_PROVIDER=openai_compatible
LLM_API_KEY=YOUR_API_KEY
LLM_BASE_URL=YOUR_BASE_URL
LLM_MODEL=YOUR_MODEL
```

Never commit real API keys to the repository.

---

## 🧪 Testing

Run the test suite:

```bash
cd backend
pytest -q
```

The project currently contains tests covering:

- API behavior
- Matching
- RAG
- CV/JD parsing
- Skills
- LLM safeguards
- Prompt injection
- Fairness safeguards

---

## 📊 Evaluation

The repository includes a small evaluation dataset for regression and sanity testing.

Example evaluation areas:

- Skill extraction
- Ranking
- Evidence verification
- Counterfactual fairness
- Matching latency

The evaluation dataset is intentionally small.

**Perfect scores on a small curated dataset must not be interpreted as proof of real-world recruitment accuracy.**

Before real-world deployment, evaluation should use a larger, independently labeled and appropriately anonymized dataset.

---

## 📁 Project Structure

```text
ai-recruitment-assistant/
│
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   ├── api/
│   │   ├── core/
│   │   ├── services/
│   │   └── utils/
│   ├── scripts/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   └── services/
│   ├── Dockerfile
│   └── package.json
│
├── data/
│   ├── eval/
│   ├── knowledge/
│   ├── sample_cvs/
│   └── sample_jobs/
│
├── docker/
│   └── init.sql
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── ai-pipeline.md
│   └── fairness-and-security.md
│
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## 📚 Documentation

Additional documentation:

- `docs/architecture.md` — System architecture
- `docs/api.md` — API documentation
- `docs/ai-pipeline.md` — AI processing pipeline
- `docs/fairness-and-security.md` — Fairness and security design

---

## ⚠️ Limitations

This project is a **decision-support system**, not an autonomous hiring system.

Known limitations include:

- Rule-based parsing can struggle with highly complex CV layouts.
- Scanned PDFs without OCR may not be readable.
- Hashing-based embeddings provide limited semantic understanding.
- Semantic thresholds require calibration.
- The evaluation dataset is small.
- Recruitment data may contain hidden demographic or socioeconomic bias.
- Production deployment requires additional security hardening.
- Employment-related AI systems may be subject to applicable legal and regulatory requirements.

Recruiters and organizations remain responsible for the final hiring decision.

---

## 🗺️ Roadmap

### Completed

- [x] CV/JD parsing
- [x] Candidate matching
- [x] Explainable scoring
- [x] Evidence extraction
- [x] Fairness safeguards
- [x] Prompt injection defense
- [x] RAG knowledge base
- [x] LLM integration
- [x] Audit trail
- [x] Batch analysis
- [x] Candidate ranking
- [x] PDF reporting
- [x] Docker deployment

### Planned

- [ ] OCR for scanned PDFs
- [ ] Alembic database migrations
- [ ] pgvector HNSW optimization
- [ ] Authentication rate limiting
- [ ] Larger independent evaluation dataset
- [ ] Bias evaluation by demographic group
- [ ] Improved user management
- [ ] Production-grade session management
- [ ] Automated security scanning in CI/CD

---

## 📄 License

Add the appropriate license before publishing the repository.

If this project is intended for public reuse, MIT, Apache-2.0, or another appropriate open-source license can be considered after reviewing the project's ownership and dependencies.

---

## ⚖️ Disclaimer

This software provides AI-assisted analysis for recruitment.

It must not be treated as an autonomous decision-maker or as a substitute for qualified human judgment.

Organizations deploying this system are responsible for ensuring compliance with applicable privacy, employment, AI, data protection, and other relevant regulations.

---

**Built for explainable, evidence-based, and human-centered AI-assisted recruitment.**