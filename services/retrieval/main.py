from fastapi import FastAPI, Depends, Query
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os, time, traceback
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel
from typing import List, Optional
from .vector_store import semantic_code_search, top_k, multi_hop, init_store
from ..shared.auth import auth_dependency

app = FastAPI(title="retrieval-service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
RETRIEVAL_LATENCY = Histogram("retrieval_query_seconds", "Retrieval query latency seconds", ["endpoint","mode"])
RETRIEVAL_ERRORS = Counter("retrieval_errors_total", "Retrieval errors", ["endpoint"])

class SearchBody(BaseModel):
    query: str
    top_k: int = 10
    hops: int = 1
    expansion_k: int = 4
    mode: str = "hybrid"  # bm25|semantic|hybrid

@app.on_event("startup")
async def _init():
    store_path = os.getenv("RAG_VECTOR_DB_PATH", "/mnt/data/rag_vectors.pkl")
    init_store(store_path)

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/tool_retrieve_rag")
def tool_retrieve_rag(body: SearchBody, dep=Depends(auth_dependency)):
    t0 = time.time()
    ep = "tool_retrieve_rag"
    try:
        if body.hops and body.hops>1:
            retrieved = multi_hop(body.query, top_k=body.top_k, hops=body.hops, expansion_k=body.expansion_k)
        else:
            retrieved = top_k(body.query, top_k=body.top_k)
        RETRIEVAL_LATENCY.labels(endpoint=ep, mode="multi" if body.hops>1 else "single").observe(time.time()-t0)
        return {"retrieved": retrieved, "query_embedding_dim": 384, "hops_used": body.hops}
    except Exception as e:
        RETRIEVAL_ERRORS.labels(endpoint=ep).inc()
        return JSONResponse({"error": "Failed to retrieve information", "detail": str(e)}, status_code=500)

@app.get("/search/code")
def search_code(q: str = Query(...), top_k: int = 10, mode: str = "hybrid", dep=Depends(auth_dependency)):
    t0 = time.time()
    ep = "search_code"
    try:
        res = semantic_code_search(os.getenv("RAG_VECTOR_DB_PATH", "/mnt/data/rag_vectors.pkl"), q, top_k=top_k, mode=mode)
        RETRIEVAL_LATENCY.labels(endpoint=ep, mode=mode).observe(time.time()-t0)
        return {"query": q, "top_k": top_k, "mode": mode, "results": res}
    except Exception as e:
        RETRIEVAL_ERRORS.labels(endpoint=ep).inc()
        return JSONResponse({"error":"search failed","detail":str(e)}, status_code=500)
