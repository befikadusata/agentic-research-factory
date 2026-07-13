import os
from pydantic_settings import BaseSettings
from logger import logger


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"

    # Legacy single-provider mode.
    # If LLM_MODEL is set, it overrides the per-agent routing below.
    LLM_PROVIDER: str = "openai-compatible"
    LLM_MODEL: str | None = None
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str | None = None

    # Provider keys used by the router.
    GROQ_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # Per-agent model OVERRIDES. Unset (None) → the agent is routed by capability
    # via llm_router.MODEL_REGISTRY / ROLE_CAPS, which picks the cheapest model
    # fit for the role from whichever providers have keys. That routing works on
    # a single provider (e.g. Groq 8B for light work, Groq 70B for reasoning),
    # so it no longer collapses when only one provider key is set. Set one of
    # these to pin a specific agent to a specific slug (it wins over routing);
    # the `openrouter/` prefix is explicit so litellm routes it correctly.
    #
    # The old default routing is now expressed as capabilities in the registry:
    #   - light (strategist, query_rewriter)        → Groq 8B-instant
    #   - reasoning/writing/tool-use (core path)     → Groq 70B-versatile
    #   - reasoning/judging, single-shot (analyst,   → OpenRouter free (Tencent
    #     reviewer, eval)                              Hunyuan hy3), when its key
    #                                                  is present; else Groq 70B.
    STRATEGIST_MODEL: str | None = None
    QUERY_REWRITER_MODEL: str | None = None
    RESEARCHER_MODEL: str | None = None
    WRITER_MODEL: str | None = None
    EDITOR_MODEL: str | None = None
    LEAD_INTEL_MODEL: str | None = None
    ANALYST_MODEL: str | None = None
    REVIEWER_MODEL: str | None = None
    EVAL_MODEL: str | None = None

    # Quality judges (the reviewer's audit + the eval-confidence judge) should
    # not be the same model as the generators they grade — a model grading its
    # own output shares its blind spots, and that self-assessment is surfaced to
    # the human as "AI Confidence." When set, JUDGE_MODEL pins the judges to a
    # distinct model in BOTH legacy and routed mode (in legacy mode every agent
    # otherwise collapses onto the single LLM_MODEL). Unset → judges follow the
    # normal resolution (legacy: LLM_MODEL; routed: REVIEWER_MODEL/EVAL_MODEL).
    # A different model on the same provider (e.g. a second Groq model) is enough
    # to break the shared blind spot without needing a second provider key. (M2)
    JUDGE_MODEL: str | None = None

    # A run stuck in a non-terminal state (pending / researching / analyzing /
    # writing, or an *autonomous* run parked at an approval gate) longer than
    # this — with no segment task advancing it — is considered orphaned and
    # reaped to `failed` by the beat-driven reaper. Must exceed the Celery hard
    # task limit (~11 min) plus a margin, so a still-running segment is never
    # mistaken for a dead one. (M3)
    RUN_STUCK_TIMEOUT_MIN: int = 20

    # Gemini embeddings for RAG.
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    EMBEDDING_DIMENSION: int = 384

    # Optional in development; required in production (enforced by validate_config).
    TAVILY_API_KEY: str | None = None
    FIRECRAWL_API_KEY: str | None = None
    LLAMA_CLOUD_API_KEY: str | None = None

    # Self-hosted alternatives. If set, these take priority over the cloud
    # providers above (no payment/geo-restricted API key required).
    SEARXNG_URL: str | None = None
    FIRECRAWL_API_URL: str | None = None

    DATABASE_URL: str
    # Under pytest (TESTING=1) the suite drops/recreates every table, so it must
    # never point at DATABASE_URL. Left unset, config auto-derives a `<db>_test`
    # sibling database; set this to override where the test schema lives.
    TEST_DATABASE_URL: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    BACKEND_JWT_SECRET: str
    NEXTAUTH_SECRET: str
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # Outbound email (verification links). If SMTP_HOST is unset, emails are
    # logged instead of sent — fine for local/dev.
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "no-reply@research-factory.local"
    SMTP_STARTTLS: bool = True

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

# When running under pytest, redirect every DB consumer (database.py's engine,
# service-layer AsyncSessionLocal, and the test fixtures alike) to an isolated
# test database. The suite drop_all/create_all's on connect, so pointing it at
# the app DB wipes real data — this guarantees it can't. conftest.py sets
# TESTING=1 before importing this module.
if os.environ.get("TESTING") == "1":
    _target = settings.TEST_DATABASE_URL
    if not _target:
        from sqlalchemy.engine import make_url
        _u = make_url(settings.DATABASE_URL)
        # str(url) masks the password as '***'; render_as_string keeps it intact.
        _target = _u.set(database=f"{_u.database}_test").render_as_string(hide_password=False)
    if _target == settings.DATABASE_URL:
        raise RuntimeError("TEST_DATABASE_URL must differ from DATABASE_URL")
    settings.DATABASE_URL = _target

_PROD_REQUIRED = ["TAVILY_API_KEY", "FIRECRAWL_API_KEY", "LLAMA_CLOUD_API_KEY"]

_FEATURE_LABEL = {
    "TAVILY_API_KEY": "web search",
    "FIRECRAWL_API_KEY": "web scraping",
    "LLAMA_CLOUD_API_KEY": "PDF parsing",
}


def validate_config(s: Settings) -> None:
    missing = [k for k in _PROD_REQUIRED if getattr(s, k) is None]
    if s.SEARXNG_URL:
        missing = [k for k in missing if k != "TAVILY_API_KEY"]
    if s.FIRECRAWL_API_URL:
        missing = [k for k in missing if k != "FIRECRAWL_API_KEY"]
    if not missing:
        return
    if s.ENVIRONMENT == "production":
        raise RuntimeError(f"Missing required production env vars: {missing}")
    for k in missing:
        logger.warning(f"{k} is not set — {_FEATURE_LABEL[k]} will be unavailable")


def _export_env(name: str, value: str | None) -> None:
    if value and not os.environ.get(name):
        os.environ[name] = value


# Make provider keys visible to libraries that read from os.environ directly.
_export_env("GROQ_API_KEY", settings.GROQ_API_KEY)
_export_env("OPENROUTER_API_KEY", settings.OPENROUTER_API_KEY)
_export_env("GEMINI_API_KEY", settings.GEMINI_API_KEY)
_export_env("GOOGLE_API_KEY", settings.GEMINI_API_KEY)
_export_env("LLM_API_KEY", settings.LLM_API_KEY)
