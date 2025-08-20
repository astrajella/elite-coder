-- 002_pgvector_documents.sql
-- Creates a documents table with pgvector column for embeddings
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY,
  title TEXT,
  text TEXT,
  embedding vector(384)
);
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
