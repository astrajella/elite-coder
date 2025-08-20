
from pydantic import BaseModel, Field, validator
from typing import Any, Dict, List, Literal, Optional
from services.common.schemas import CodePatchList, FilePatch, ErrorResponse

# Canonical tool output envelope every tool must return
class ToolOutput(BaseModel):
    tool: str = Field(..., description="Tool name (e.g., tool_generate_code)")
    status: Literal['ok','error'] = 'ok'
    schema_name: str = Field(..., description="Name of the schema used to validate payload")
    payload: Dict[str, Any] = Field(default_factory=dict)
    started_at: float = Field(..., description="Epoch seconds")
    finished_at: float = Field(..., description="Epoch seconds")
    duration_ms: int = Field(..., ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    tokens_input: int = Field(default=0, ge=0)
    tokens_output: int = Field(default=0, ge=0)
    persona: Optional[str] = None
    run_id: Optional[str] = None
    step_id: Optional[str] = None

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
    failures: List[TestFailure] = []
    logs_url: Optional[str] = None

# Map names to models for validation
SCHEMAS = {
    'CodePatchList': CodePatchList,
    'SummarizerSchema': SummarizerSchema,
    'PlanSchema': PlanSchema,
    'TestResultsSchema': TestResultsSchema,
}

def validate_tool_payload(schema_name: str, payload: dict):
    if schema_name not in SCHEMAS:
        raise ValueError(f'Unknown schema: {schema_name}')
    model = SCHEMAS[schema_name]
    return model(**payload)  # will raise on validation error
