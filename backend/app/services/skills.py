"""Taxonomy skill: nama kanonik -> (kategori, alias). Dipakai untuk normalisasi
(mis. "ML" == "Machine Learning") sehingga matching tidak bergantung pada kata yang persis sama."""
import re
from functools import lru_cache

# (canonical, category, [aliases])
_RAW: list[tuple[str, str, list[str]]] = [
    # Bahasa pemrograman
    ("Python", "language", ["python3"]),
    ("Java", "language", []),
    ("JavaScript", "language", ["js", "ecmascript"]),
    ("TypeScript", "language", ["ts"]),
    ("C++", "language", ["cpp"]),
    ("C#", "language", ["csharp", "c sharp"]),
    ("Go", "language", ["golang"]),
    ("Rust", "language", []),
    ("PHP", "language", []),
    ("Kotlin", "language", []),
    ("Swift", "language", []),
    ("Scala", "language", []),
    ("SQL", "language", ["t-sql", "pl/sql"]),
    ("R", "language", ["r programming", "r language"]),
    # AI / ML
    ("Machine Learning", "ai", ["ml", "pembelajaran mesin", "classification model", "classifier", "predictive model", "regression model", "model training", "trained models", "trained and evaluated"]),
    ("Deep Learning", "ai", ["dl", "neural network", "neural networks", "jaringan saraf"]),
    ("NLP", "ai", ["natural language processing", "pemrosesan bahasa alami", "text mining"]),
    ("Computer Vision", "ai", ["image recognition", "image classification", "object detection", "visi komputer"]),
    ("CNN", "ai", ["convolutional neural network", "convolutional neural networks"]),
    ("RNN", "ai", ["recurrent neural network", "lstm"]),
    ("Transformers", "ai", ["transformer", "bert", "gpt"]),
    ("LLM", "ai", ["large language model", "large language models", "llms"]),
    ("RAG", "ai", ["retrieval augmented generation", "retrieval-augmented generation"]),
    ("Prompt Engineering", "ai", ["prompt design"]),
    ("Reinforcement Learning", "ai", ["rl"]),
    ("Time Series", "ai", ["time-series", "forecasting", "peramalan"]),
    ("Recommender Systems", "ai", ["recommendation system", "recommendation systems", "recommender system"]),
    ("MLOps", "ai", ["ml ops", "model deployment"]),
    ("TensorFlow", "framework", ["tf", "keras"]),
    ("PyTorch", "framework", ["torch"]),
    ("Scikit-learn", "framework", ["sklearn", "scikit learn"]),
    ("Hugging Face", "framework", ["huggingface"]),
    ("LangChain", "framework", []),
    ("LlamaIndex", "framework", ["llama index"]),
    ("OpenCV", "framework", ["open cv"]),
    ("spaCy", "framework", ["spacy"]),
    ("XGBoost", "framework", ["lightgbm", "gradient boosting"]),
    # Data
    ("Pandas", "data", []),
    ("NumPy", "data", ["numpy"]),
    ("Data Analysis", "data", ["data analytics", "analisis data"]),
    ("Data Visualization", "data", ["visualisasi data", "tableau", "power bi", "matplotlib"]),
    ("Data Engineering", "data", ["etl", "data pipeline", "data pipelines"]),
    ("Apache Spark", "data", ["spark", "pyspark"]),
    ("Apache Airflow", "data", ["airflow"]),
    ("Statistics", "data", ["statistik", "statistical analysis"]),
    # Backend / web
    ("FastAPI", "backend", []),
    ("Flask", "backend", []),
    ("Django", "backend", []),
    ("Node.js", "backend", ["nodejs", "node js", "node"]),
    ("Spring Boot", "backend", ["spring"]),
    ("Laravel", "backend", []),
    ("REST API", "backend", ["restful api", "rest apis", "restful", "api development", "web api"]),
    ("GraphQL", "backend", []),
    ("Microservices", "backend", ["microservice", "arsitektur microservices"]),
    ("gRPC", "backend", []),
    # Frontend
    ("React", "frontend", ["reactjs", "react.js", "react js"]),
    ("Next.js", "frontend", ["nextjs", "next js"]),
    ("Vue.js", "frontend", ["vue", "vuejs"]),
    ("Angular", "frontend", []),
    ("HTML/CSS", "frontend", ["html", "css", "html5", "css3"]),
    ("Tailwind CSS", "frontend", ["tailwind"]),
    # Database
    ("PostgreSQL", "database", ["postgres", "postgresql", "psql"]),
    ("MySQL", "database", ["mariadb"]),
    ("MongoDB", "database", ["mongo"]),
    ("Redis", "database", []),
    ("Elasticsearch", "database", ["elastic search", "opensearch"]),
    ("Vector Database", "database", ["pgvector", "pinecone", "weaviate", "milvus", "qdrant", "chroma", "faiss", "vector db", "vector store"]),
    # DevOps / cloud
    ("Docker", "devops", ["container", "containerization", "dockerfile", "docker compose"]),
    ("Kubernetes", "devops", ["k8s"]),
    ("CI/CD", "devops", ["ci cd", "github actions", "gitlab ci", "jenkins"]),
    ("Git", "devops", ["github", "gitlab", "version control"]),
    ("Linux", "devops", ["ubuntu", "bash"]),
    ("AWS", "cloud", ["amazon web services", "ec2", "s3", "sagemaker"]),
    ("GCP", "cloud", ["google cloud", "google cloud platform", "vertex ai"]),
    ("Azure", "cloud", ["microsoft azure"]),
    ("Terraform", "devops", []),
    # Testing & praktik
    ("Pytest", "testing", ["unit testing", "unit test", "pengujian unit"]),
    ("Agile", "practice", ["scrum", "kanban"]),
    ("System Design", "practice", ["software architecture", "arsitektur sistem"]),
    # Kompetensi non-teknis
    ("Communication", "soft", ["komunikasi", "presentation", "presentasi"]),
    ("Leadership", "soft", ["kepemimpinan", "team lead", "tech lead", "memimpin tim"]),
    ("Problem Solving", "soft", ["pemecahan masalah", "analytical thinking"]),
    ("Project Management", "soft", ["manajemen proyek", "product management"]),
]

# Akronim pendek: hanya cocok bila ditulis HURUF BESAR (mis. "ML", bukan "ml").
_ACRONYMS = {"ml", "dl", "rl", "tf", "js", "ts", "cpp"}
# Kata umum yang ambigu: tidak dipakai untuk deteksi bebas (tetap dikenali bila muncul di daftar skill).
_SKIP_FREE = {"go", "node", "spring", "container", "torch", "s3", "mongo"}
# Simbol/akronim yang harus persis (case-sensitive).
_CASE_SENSITIVE = {"R", "C++", "C#", "SQL", "AWS", "GCP", "NLP", "LLM", "RAG", "CNN", "RNN", "LLMs"}


def _pattern(term: str, case_sensitive: bool) -> re.Pattern:
    esc = re.escape(term)
    # batas kata yang aman untuk simbol seperti C++ / C# / Node.js
    return re.compile(rf"(?<![A-Za-z0-9+#]){esc}(?![A-Za-z0-9]|\+\+|#)", 0 if case_sensitive else re.IGNORECASE)


class SkillTaxonomy:
    def __init__(self) -> None:
        self.category: dict[str, str] = {}
        self._patterns: list[tuple[str, re.Pattern]] = []
        self._alias_to_canon: dict[str, str] = {}
        for canon, cat, aliases in _RAW:
            self.category[canon] = cat
            self._alias_to_canon[canon.lower()] = canon
            terms = [canon] + aliases
            for t in terms:
                self._alias_to_canon[t.lower()] = canon
                tl = t.lower()
                if tl in _SKIP_FREE:
                    continue
                if tl in _ACRONYMS:
                    self._patterns.append((canon, _pattern(t.upper(), True)))
                elif t in _CASE_SENSITIVE:
                    self._patterns.append((canon, _pattern(t, True)))
                else:
                    self._patterns.append((canon, _pattern(t, False)))

    def canonical(self, term: str) -> str | None:
        return self._alias_to_canon.get(term.strip().lower())

    def find(self, text: str) -> list[str]:
        """Semua skill kanonik yang disebut dalam teks (urutan kemunculan, unik)."""
        hits: dict[str, int] = {}
        for canon, pat in self._patterns:
            m = pat.search(text)
            if m and (canon not in hits or m.start() < hits[canon]):
                hits[canon] = m.start()
        return [c for c, _ in sorted(hits.items(), key=lambda kv: kv[1])]

    def aliases_of(self, canon: str) -> list[str]:
        return [a for a, c in self._alias_to_canon.items() if c == canon]


# Konsep yang tersirat: menyebut kunci berarti (secara wajar) menyentuh konsep di kanan.
IMPLIES: dict[str, list[str]] = {
    "CNN": ["Deep Learning", "Computer Vision", "Machine Learning"],
    "RNN": ["Deep Learning", "Machine Learning"],
    "TensorFlow": ["Deep Learning", "Machine Learning"],
    "PyTorch": ["Deep Learning", "Machine Learning"],
    "Deep Learning": ["Machine Learning"],
    "Computer Vision": ["Machine Learning"],
    "OpenCV": ["Computer Vision"],
    "Scikit-learn": ["Machine Learning"],
    "XGBoost": ["Machine Learning"],
    "Transformers": ["NLP", "Deep Learning", "Machine Learning"],
    "Hugging Face": ["NLP", "Machine Learning"],
    "spaCy": ["NLP"],
    "LLM": ["NLP", "Machine Learning"],
    "RAG": ["LLM", "Vector Database", "NLP"],
    "LangChain": ["LLM"],
    "LlamaIndex": ["LLM"],
    "FastAPI": ["REST API"],
    "Flask": ["REST API"],
    "Django": ["REST API"],
    "Spring Boot": ["REST API"],
    "Node.js": ["REST API"],
    "Kubernetes": ["Docker"],
    "Data Visualization": ["Data Analysis"],
    "Pandas": ["Data Analysis"],
    "Apache Spark": ["Data Engineering"],
    "Apache Airflow": ["Data Engineering"],
    "Recommender Systems": ["Machine Learning"],
    "Time Series": ["Machine Learning"],
}

# Keluarga teknologi setara: skill berbeda di keluarga yang sama = "related" (kredit parsial).
RELATED_GROUPS: list[set[str]] = [
    {"TensorFlow", "PyTorch"},
    {"PostgreSQL", "MySQL", "SQL"},
    {"AWS", "GCP", "Azure"},
    {"React", "Vue.js", "Angular", "Next.js"},
    {"FastAPI", "Flask", "Django", "Spring Boot", "Laravel", "Node.js"},
    {"Docker", "Kubernetes"},
    {"Machine Learning", "Deep Learning", "Scikit-learn", "XGBoost"},
    {"NLP", "Transformers", "LLM", "spaCy", "Hugging Face", "RAG"},
    {"CNN", "Computer Vision", "OpenCV", "Deep Learning"},
    {"Data Analysis", "Pandas"},
    {"MongoDB", "PostgreSQL", "MySQL", "Redis"},
    {"Vector Database", "Elasticsearch"},
    {"Apache Spark", "Data Engineering", "Apache Airflow"},
    {"Python", "R"},
    {"Java", "Kotlin", "Scala"},
    {"REST API", "GraphQL", "gRPC", "Microservices"},
]


def implied(canon: str) -> list[str]:
    return IMPLIES.get(canon, [])


def related_skills(canon: str) -> set[str]:
    out: set[str] = set()
    for g in RELATED_GROUPS:
        if canon in g:
            out |= g
    out.discard(canon)
    return out


@lru_cache
def get_taxonomy() -> SkillTaxonomy:
    return SkillTaxonomy()
