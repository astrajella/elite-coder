-- pgvector migration: create documents table with vector column
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY,
  title TEXT,
  text TEXT,
  embedding vector(384)
);
-- index for similarity search
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
