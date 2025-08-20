
#!/usr/bin/env python3
"""
Build or rebuild the vector store index from docs folder.
"""
import os
from services.retrieval.vector_store import VectorStore

if __name__ == "__main__":
    base = os.getenv("WORK_DIR", ".")
    docs_dir = os.path.join(base, "docs")
    db_path = os.getenv("RAG_VECTOR_DB_PATH", "./data/rag_vectors")
    store = VectorStore(db_path)
    texts = []
    for root, dirs, files in os.walk(docs_dir):
        for f in files:
            if f.lower().endswith((".md", ".txt", ".rst")):
                p = os.path.join(root, f)
                try:
                    with open(p, "r", encoding="utf-8") as fh:
                        texts.append(f"{f}\\n" + fh.read())
                except Exception:
                    pass
    if texts:
        store.add_documents(texts)
        print("Indexed", len(texts), "documents to", db_path)
    else:
        print("No docs found in", docs_dir)
