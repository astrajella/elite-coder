#!/usr/bin/env python3
import os, glob, json, sys
from services.retrieval.pgvector_store import PgVectorStore

RAG_DOCS_DIR = os.getenv('RAG_DOCS_DIR', './docs')
PG_CONN = os.getenv('PG_CONN', '')

if not PG_CONN:
    print('PG_CONN not set. Set PG_CONN environment variable to your Postgres connection string.')
    sys.exit(1)

store = PgVectorStore(PG_CONN)
print('Initializing table...')
store.init_table()

docs = []
for root, dirs, files in os.walk(RAG_DOCS_DIR):
    for f in files:
        if f.endswith('.md') or f.endswith('.txt') or f.endswith('.rst'):
            path = os.path.join(root,f)
            with open(path, 'r', encoding='utf-8') as fh:
                txt = fh.read().strip()
            docs.append((f, txt[:10000]))

if not docs:
    print('No docs found in', RAG_DOCS_DIR)
else:
    print('Indexing', len(docs), 'documents...')
    store.add_documents(docs)
    print('Done.')
