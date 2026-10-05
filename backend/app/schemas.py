from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)  # str (bukan EmailStr) agar domain internal tetap dapat login
    password: str


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="recruiter", pattern="^(admin|recruiter)$")


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=30, max_length=20000)


class AnalyzeIn(BaseModel):
    candidate_id: int
    job_id: int


class BatchIn(BaseModel):
    job_id: int
    candidate_ids: list[int] | None = None  # None = semua kandidat


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
