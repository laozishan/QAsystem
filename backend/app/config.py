import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings:
    app_name = "AI Knowledge QA"
    cors_origins = [
        origin.strip()
        for origin in os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
    embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    llm_api_key = deepseek_api_key or openai_api_key
    llm_base_url = "https://api.deepseek.com" if deepseek_api_key else None
    llm_model = deepseek_model if deepseek_api_key else openai_model
    sqlite_path = DATA_DIR / "qasystem.sqlite3"
    chroma_path = DATA_DIR / "chroma"
    retrieval_k = int(os.getenv("RETRIEVAL_K", "5"))


settings = Settings()
