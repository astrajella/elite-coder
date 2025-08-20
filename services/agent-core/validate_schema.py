
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Type
from services.common.schemas import (
    PlanSchema, CodePatchList, TestResultsSchema, SummarizerSchema,
    RetrievalSchema, LedgerRunSchema, RefactorPatchSchema, ErrorResponse
)

SCHEMA_MAP: Dict[str, Type[BaseModel]] = {
    "PlanSchema": PlanSchema,
    "CodePatchList": CodePatchList,
    "TestResultsSchema": TestResultsSchema,
    "SummarizerSchema": SummarizerSchema,
    "RetrievalSchema": RetrievalSchema,
    "LedgerRunSchema": LedgerRunSchema,
    "RefactorPatchSchema": RefactorPatchSchema,
    "ErrorResponse": ErrorResponse,
}

class ValidateRequest(BaseModel):
    schema_name: str
    payload: dict

app = FastAPI(title="Schema Validator")

@app.post("/tool_validate_schema")
def tool_validate_schema(req: ValidateRequest):
    schema_name = req.schema_name
    if schema_name not in SCHEMA_MAP:
        raise HTTPException(status_code=400, detail={"message": "Unknown schema", "schema": schema_name})
    Schema = SCHEMA_MAP[schema_name]
    try:
        obj = Schema(**req.payload)
    except Exception as e:
        # Pydantic prints nested details; return stringified for now
        raise HTTPException(status_code=422, detail={"message": "Schema validation failed", "error": str(e)})
    return {"valid": True}
