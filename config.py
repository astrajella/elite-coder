import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_DEFAULT_MODEL = os.getenv("OPENROUTER_DEFAULT_MODEL", "openrouter/auto")
    MODEL_CODER = os.getenv("MODEL_CODER") or OPENROUTER_DEFAULT_MODEL
    MODEL_CRITIC = os.getenv("MODEL_CRITIC") or OPENROUTER_DEFAULT_MODEL
    MODEL_SUMMARIZER = os.getenv("MODEL_SUMMARIZER") or OPENROUTER_DEFAULT_MODEL
    RAG_VECTOR_DB_PATH = os.getenv("RAG_VECTOR_DB_PATH", "/mnt/data/ai-code-agent-elite/rag_store.pkl")
    ALLOW_INTERNET = os.getenv("ALLOW_INTERNET", "false").lower() == "true"
    PRICE_PER_1K_INPUT = float(os.getenv("PRICE_PER_1K_INPUT", "0.002"))
    PRICE_PER_1K_OUTPUT = float(os.getenv("PRICE_PER_1K_OUTPUT", "0.008"))

settings = Settings()
