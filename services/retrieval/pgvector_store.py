"""PgVectorStore backend for RAG.
Requires:
  - psycopg2-binary
  - pgvector extension enabled in Postgres
Environment variables:
  - PG_CONN (Postgres connection string)
  - RAG_VECTOR_DB_PATH not used for pgvector backend
Usage: instantiate PgVectorStore(PG_CONN) and use add_documents, search, delete, list_docs
"""
import os, pickle, math
from sentence_transformers import SentenceTransformer
import numpy as np

try:
    import psycopg2
    from psycopg2.extras import execute_values
except Exception as e:
    psycopg2 = None

EMBED_DIM = 384

class PgVectorStore:
    def __init__(self, conn_str=None, table='documents'):
        self.conn_str = conn_str or os.getenv('PG_CONN') or os.getenv('LEDGER_DB_URL') or ''
        if not self.conn_str:
            raise RuntimeError('PG_CONN not set for PgVectorStore')
        if psycopg2 is None:
            raise RuntimeError('psycopg2 not installed; please pip install psycopg2-binary')
        self.table = table
        self.model = SentenceTransformer(os.getenv('RAG_MODEL_NAME','all-MiniLM-L6-v2'))

    def _connect(self):
        return psycopg2.connect(self.conn_str)

    def init_table(self):
        sql = f"""CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS {self.table} (
  id SERIAL PRIMARY KEY,
  title TEXT,
  text TEXT,
  embedding vector({EMBED_DIM})
);
CREATE INDEX IF NOT EXISTS idx_{self.table}_embedding ON {self.table} USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"""
        conn = self._connect(); cur = conn.cursor()
        cur.execute(sql); conn.commit(); conn.close()

    def add_documents(self, docs):
        """docs: list of (title,text) tuples"""
        texts = [d[1] for d in docs]
        embs = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        # normalize embeddings
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms[norms==0] = 1.0
        embs = embs / norms
        rows = [(docs[i][0], docs[i][1], embs[i].tolist()) for i in range(len(docs))]
        conn = self._connect(); cur = conn.cursor()
        execute_values(cur,
            f"INSERT INTO {self.table} (title,text,embedding) VALUES %s",
            rows,
            template = "(%s,%s,%s::vector)"
        )
        conn.commit(); conn.close()

    def search(self, query, top_k=5):
        q_emb = self.model.encode([query], show_progress_bar=False, convert_to_numpy=True)[0]
        q_emb = q_emb / (np.linalg.norm(q_emb) or 1.0)
        # use inner product with vector column via pgvector operator <#> for cosine distance or <-> for Euclidean depending on pgvector version.
        sql = f"SELECT id, title, text, 1 - (embedding <#> %s::vector) AS score FROM {self.table} ORDER BY embedding <#> %s::vector LIMIT %s"
        conn = self._connect(); cur = conn.cursor()
        cur.execute(sql, (q_emb.tolist(), q_emb.tolist(), top_k))
        rows = cur.fetchall(); conn.close()
        results = [{'id': str(r[0]), 'title': r[1], 'text': r[2], 'score': float(r[3])} for r in rows]
        return results

    def list_docs(self, limit=100):
        conn = self._connect(); cur = conn.cursor(); cur.execute(f"SELECT id,title FROM {self.table} ORDER BY id DESC LIMIT %s", (limit,))
        rows = cur.fetchall(); conn.close()
        return [{'id': r[0], 'title': r[1]} for r in rows]
