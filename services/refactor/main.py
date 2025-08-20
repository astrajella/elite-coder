
import os, io, json, ast
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime

try:
    from services.orchestrator.main import auth_dependency
except Exception:
    async def auth_dependency():
        return True

class FilePatch(BaseModel):
    path: str
    type: str = Field(regex="^(create|replace|patch)$")
    content: str

class CodePatchList(BaseModel):
    plan_id: str = "refactor"
    step_id: str = "single"
    patches: List[FilePatch]
    author: Optional[str] = "coder_agent"
    explain: Optional[str] = None

router = APIRouter()

def _syntax_ok(path: str, content: str) -> bool:
    if path.endswith(".py"):
        try:
            ast.parse(content)
            return True
        except Exception:
            return False
    return True

@router.post("/refactor/preview")
async def refactor_preview(file_path: str, instruction: str, dep=Depends(auth_dependency)):
    p = Path(file_path)
    if not p.exists():
        raise HTTPException(404, f"File not found: {file_path}")
    original = p.read_text(encoding="utf-8")
    header = f"# Refactor note: {instruction}\n"
    new_content = header + original if not original.startswith(header) else original
    if not _syntax_ok(file_path, new_content):
        raise HTTPException(422, "Invalid syntax after refactor")
    patch = CodePatchList(patches=[FilePatch(path=file_path, type="replace", content=new_content)], explain="Safe preview patch")
    return json.loads(patch.json())

@router.post("/refactor/apply")
async def refactor_apply(payload: CodePatchList, dep=Depends(auth_dependency)):
    applied = []
    for fp in payload.patches:
        if fp.type not in ("create","replace"):
            raise HTTPException(400, "Only create/replace allowed in safe mode")
        target = Path(fp.path)
        if fp.type=="create" and target.exists():
            raise HTTPException(409, f"File already exists: {fp.path}")
        if not _syntax_ok(fp.path, fp.content):
            raise HTTPException(422, f"Syntax check failed: {fp.path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fp.content, encoding="utf-8")
        applied.append(fp.path)
    return {"applied": applied, "count": len(applied), "when": datetime.utcnow().isoformat()+"Z", "author": payload.author or "coder_agent"}

def mount(app: FastAPI):
    app.include_router(router, prefix="")
