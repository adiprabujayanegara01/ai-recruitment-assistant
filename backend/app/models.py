"""Skema database. Mengikuti bagian 10 dokumen, ditambah tabel untuk RAG, audit, dan monitoring."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="recruiter")  # admin | recruiter
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    location: Mapped[str | None] = mapped_column(String(255))
    total_experience_years: Mapped[float] = mapped_column(Float, default=0.0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    resume: Mapped["Resume"] = relationship(back_populates="candidate", cascade="all, delete-orphan", uselist=False)
    educations: Mapped[list["Education"]] = relationship(cascade="all, delete-orphan")
    experiences: Mapped[list["Experience"]] = relationship(cascade="all, delete-orphan")
    certifications: Mapped[list["Certification"]] = relationship(cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(cascade="all, delete-orphan")
    skills: Mapped[list["CandidateSkill"]] = relationship(cascade="all, delete-orphan")
    results: Mapped[list["MatchingResult"]] = relationship(cascade="all, delete-orphan", back_populates="candidate")


class Resume(Base):
    __tablename__ = "resumes"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(10))
    raw_text: Mapped[str] = mapped_column(Text)
    parsed: Mapped[dict] = mapped_column(JSON, default=dict)
    parser_version: Mapped[str] = mapped_column(String(40))
    candidate: Mapped[Candidate] = relationship(back_populates="resume")


class Education(Base):
    __tablename__ = "educations"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    institution: Mapped[str | None] = mapped_column(String(255))
    degree: Mapped[str | None] = mapped_column(String(255))
    major: Mapped[str | None] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer, default=0)


class Experience(Base):
    __tablename__ = "experiences"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    company: Mapped[str | None] = mapped_column(String(255))
    position: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    start: Mapped[str | None] = mapped_column(String(10))
    end: Mapped[str | None] = mapped_column(String(10))
    months: Mapped[int] = mapped_column(Integer, default=0)


class Certification(Base):
    __tablename__ = "certifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str | None] = mapped_column(String(255))


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(60), default="other")


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    skill: Mapped[Skill] = relationship()


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)  # hasil JD parser
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    job_skills: Mapped[list["JobSkill"]] = relationship(cascade="all, delete-orphan")
    results: Mapped[list["MatchingResult"]] = relationship(cascade="all, delete-orphan", back_populates="job")


class JobSkill(Base):
    __tablename__ = "job_skills"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    skill: Mapped[Skill] = relationship()


class MatchingResult(Base):
    __tablename__ = "matching_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    match_score: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text, default="")
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)  # output LLM tervalidasi
    versions: Mapped[dict] = mapped_column(JSON, default=dict)  # embedding/llm/prompt/engine
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    candidate: Mapped[Candidate] = relationship(back_populates="results")
    job: Mapped[Job] = relationship(back_populates="results")
    details: Mapped[list["MatchingDetail"]] = relationship(cascade="all, delete-orphan", order_by="MatchingDetail.id")


class MatchingDetail(Base):
    __tablename__ = "matching_details"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("matching_results.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(255))  # requirement
    kind: Mapped[str] = mapped_column(String(20), default="skill")  # skill | responsibility
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence: Mapped[str | None] = mapped_column(Text)
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20))  # matched | related | not_identified
    method: Mapped[str] = mapped_column(String(60), default="")  # exact | declared | related:X | semantic
    evidence_section: Mapped[str | None] = mapped_column(String(30))


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(60), default="general")
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)
    embedding_model: Mapped[str] = mapped_column(String(120))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InferenceLog(Base):
    """Monitoring bagian 16: satu baris per analisis."""
    __tablename__ = "inference_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    candidate_id: Mapped[int | None] = mapped_column(Integer)
    job_id: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(120))
    llm_model: Mapped[str] = mapped_column(String(120))
    matching_engine_version: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(40))
    processing_ms: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    unsupported_claims: Mapped[int] = mapped_column(Integer, default=0)
    llm_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
