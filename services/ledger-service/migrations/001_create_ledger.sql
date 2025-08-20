
-- ledger pg migration
CREATE EXTENSION IF NOT EXISTS vector; -- harmless if not used
CREATE TABLE IF NOT EXISTS runs (
  id SERIAL PRIMARY KEY,
  persona TEXT,
  tool TEXT,
  duration REAL,
  tokens INTEGER,
  cost REAL,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS daily_aggregates (
  id SERIAL PRIMARY KEY,
  date TEXT UNIQUE,
  total_runs INTEGER DEFAULT 0,
  total_tokens INTEGER DEFAULT 0,
  total_cost REAL DEFAULT 0.0
);
