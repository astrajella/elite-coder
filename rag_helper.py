
import os, pickle, hashlib, time
from typing import List, Dict, Any
# Reusable RAG helper that wraps the persistent VectorStore implementation.
from services.retrieval.vector_store import SimpleVectorStore as VectorStore

MODEL_NAME = os.getenv("RAG_MODEL_NAME", "all-MiniLM-L6-v2")
DEFAULT_DB_PATH = os.getenv("RAG_VECTOR_DB_PATH", "./data/rag_vectors")

class RagStore:
    def __init__(self, path: str = None, model_name: str = None):
        self.path = path or DEFAULT_DB_PATH
        self.model_name = model_name or MODEL_NAME
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        # The underlying SimpleVectorStore does not accept a model_name, so we don't pass it.
        self.store = VectorStore(self.path)
    def seed_from_folder(self, folder: str):
        # read text files from folder and add to store
        texts = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith((".md", ".txt", ".rst")):
                    p = os.path.join(root, f)
                    try:
                        with open(p, "r", encoding="utf-8") as fh:
                            texts.append(f"FILE:{f}\\n" + fh.read())
                    except Exception:
                        pass
        if texts:
            self.store.add_documents(texts)
    def add(self, docs: List[str], ids: List[str] = None):
        self.store.add_documents(docs, ids)
    def drop(self, ids: List[str]):
        self.store.delete_by_ids(ids)
    def top_k(self, query: str, top_k: int = 3):
        return self.store.search(query, top_k=top_k)
    def multi_hop(self, query: str, top_k: int = 3, hops: int = 2, expansion_k: int = 2):
        return self.store.multi_hop(query, top_k=top_k, hops=hops, expansion_k=expansion_k)
    @property
    def docs(self):
        return self.store.docs
