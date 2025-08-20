from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional, Any

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
    details: Optional[dict] = None

class SummarizerSchema(BaseModel):
    summary: str
    token_est: int
    important_docs: List[str]
    drop_list: List[str]
