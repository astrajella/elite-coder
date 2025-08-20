
import os, hashlib
from typing import List, Dict, Any

ROOT = os.getenv("WORK_DIR", ".")

def _abs(path: str) -> str:
    base = os.path.abspath(ROOT)
    full = os.path.abspath(os.path.join(base, path))
    if not full.startswith(base):
        raise ValueError("Forbidden path")
    return full

def apply_patches(patches: List[Dict[str, Any]]) -> Dict[str, Any]:
    applied = []
    skipped = []
    for p in patches:
        path = p["path"]
        content = p["content"]
        full = _abs(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        existing = ""
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8", errors="ignore") as f:
                existing = f.read()
        if existing == content:
            skipped.append({"path": path, "reason":"identical"})
            continue
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        applied.append({"path": path, "bytes": len(content)})
    return {"applied": applied, "skipped": skipped}
