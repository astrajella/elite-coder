#!/usr/bin/env python3
import os, glob, pathlib, json
from services.retrieval.vector_store import init_store, add_documents

def gather_docs(docs_dir='docs'):
    docs = []
    for p in glob.glob(os.path.join(docs_dir, '**/*.*'), recursive=True):
        try:
            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                docs.append(f.read())
        except Exception:
            continue
    return docs

if __name__ == '__main__':
    ds = gather_docs()
    print('Found', len(ds), 'documents. Adding to vector store...')
    add_documents(ds)
    print('Done. Persisted to', os.getenv('RAG_VECTOR_DB_PATH','/mnt/data/rag_vectors.pkl'))
