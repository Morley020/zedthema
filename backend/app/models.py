"""Request models used by the API.

Pydantic checks incoming data before it reaches the database.  This prevents
simple mistakes such as missing project titles or invalid confidence scores.
"""
from typing import Optional, List
from pydantic import BaseModel, Field

class ProjectIn(BaseModel):
    title: str
    description: str = ""
    research_question: str = ""
    framework: str = ""
    method: str = "Thematic analysis"
    languages: List[str] = Field(default_factory=lambda: ["en"])

class CodeIn(BaseModel):
    name: str
    definition: str = ""
    inclusion: str = ""
    exclusion: str = ""
    example: str = ""
    parent_id: Optional[str] = None
    theory: str = ""
    color: Optional[str] = None

class CodeUpdate(BaseModel):
    name: Optional[str] = None
    definition: Optional[str] = None
    inclusion: Optional[str] = None
    exclusion: Optional[str] = None
    example: Optional[str] = None
    parent_id: Optional[str] = None
    theory: Optional[str] = None
    color: Optional[str] = None

class URLIn(BaseModel):
    url: str
    language: str = "auto"

class PathIn(BaseModel):
    path: str
    language: str = "auto"

class ReviewIn(BaseModel):
    status: str
    code_name: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    rationale: Optional[str] = None

class AnomalyIn(BaseModel):
    label: str
    description: str = ""
    metric: str = ""
    value: str = ""
    context: str = ""

class SearchIn(BaseModel):
    query: str
    limit: int = Field(default=20, ge=1, le=100)

class CompareIn(BaseModel):
    a: List[dict] = Field(default_factory=list)
    b: List[dict] = Field(default_factory=list)
    unit: str = "segment"

class LoginIn(BaseModel):
    email: str
    password: str

class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=10)
    display_name: str = "Researcher"

class MemberIn(BaseModel):
    email: str
    role: str = "researcher"

class DualCodeIn(BaseModel):
    models: List[str] = Field(min_length=2, max_length=2)
