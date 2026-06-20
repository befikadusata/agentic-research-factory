from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_PROVIDER: str = "openai-compatible"
    LLM_MODEL: str
    LLM_API_KEY: str
    LLM_BASE_URL: str | None = None
    TAVILY_API_KEY: str
    FIRECRAWL_API_KEY: str
    LLAMA_CLOUD_API_KEY: str
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    BACKEND_JWT_SECRET: str
    NEXTAUTH_SECRET: str
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # V2 — 14.1 Persistent Vector DB
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None
    SUPABASE_DB_URL: str | None = None

    # Langfuse for observability
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
