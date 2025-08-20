from pydantic import BaseModel
from typing import List, Literal, Optional, Any, Dict

class FilePatch(BaseModel):
    path: str
    type: Literal['create','replace','patch']
    content: str

class CodePatchList(BaseModel):
    plan_id: str
    step_id: str
    patches: List[FilePatch]
    author: Optional[str] = 'coder_agent'
    explain: Optional[str] = None

class ErrorResponse(BaseModel):
    code: int
    message: str
    details: Optional[Dict[str, Any]] = None

class SummarizerSchema(BaseModel):
    summary: str
    token_est: int
    important_docs: List[str]
    drop_list: List[str]

class PlanStep(BaseModel):
    step_id: str
    description: str
    estimated_effort: Literal['low','med','high']

class PlanSchema(BaseModel):
    plan_id: str
    steps: List[PlanStep]
    priority: int

class TestFailure(BaseModel):
    test: str
    trace: str

class TestResultsSchema(BaseModel):
    passed: int
    failed: int
    failures: List[TestFailure]
    logs_url: Optional[str] = None
