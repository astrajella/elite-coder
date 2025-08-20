
from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional, Any, Dict

class FilePatch(BaseModel):
    path: str
    type: Literal["create", "replace", "patch"]
    content: str

class CodePatchList(BaseModel):
    plan_id: str = "unknown"
    step_id: str = "unknown"
    patches: List[FilePatch]
    author: Optional[str] = "coder_agent"
    explain: Optional[str] = None

class ErrorResponse(BaseModel):
    code: int
    message: str
    details: Optional[dict] = None

class PlanStep(BaseModel):
    step_id: str
    description: str
    estimated_effort: Literal["low","med","high"] = "med"

class PlanSchema(BaseModel):
    plan_id: str
    steps: List[PlanStep]
    priority: int = 0

class TestFailure(BaseModel):
    test: str
    trace: str

class TestResultsSchema(BaseModel):
    passed: int
    failed: int
    failures: List[TestFailure] = []
    logs_url: Optional[str] = None

class SummarizerSchema(BaseModel):
    summary: str
    token_est: int
    important_docs: List[str] = []
    drop_list: List[str] = []

class CriticPatchRequest(BaseModel):
    step_id: str
    patch_request: Dict[str, Any]

class CriticReview(BaseModel):
    verdict: Literal["accept","revise","block"]
    notes: str = ""
    fix_recommendations: List[CriticPatchRequest] = []

class LedgerRun(BaseModel):
    run_id: str
    persona: str
    tool: str
    tokens: float = 0.0
    cost: float = 0.0
    duration: float = 0.0
    status: Literal["success","failure","error"] = "success"
    meta: Dict[str, Any] = {}
