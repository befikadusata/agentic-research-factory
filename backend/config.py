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
    # The default routing is expressed as capabilities in the registry:
    #   - light (strategist, query_rewriter)        → Groq 8B-instant
    #   - reasoning/writing/tool-use (core path)     → Groq 70B-versatile
    #   - reasoning/judging (analyst, reviewer,      → Groq 70B-versatile
    #     eval)
    # OpenRouter's free Tencent hy3 is a reasoning model that returns empty
    # `content` under real crewai load (fails the stage), so it is NOT a routed
    # primary — it stays only as the cross-provider *fallback* slug and for
    # pricing (see services/llm_router.py). Set a *_MODEL override to pin a
    # specific slug (e.g. a paid reasoning model for the judges).
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

    # Celery per-task limits, and the LLM budget derived from them. These live
    # together because they have to stay consistent: the retry budget used to be
    # set independently (LLM_STAGE_TIMEOUT_SEC x 3 tenacity attempts = 900s, and a
    # resumed segment makes two such calls ≈ 1800s) against a 600s soft limit, so
    # a slow stage was SIGKILLed mid-flight and the run sat non-terminal until the
    # RUN_STUCK_TIMEOUT_MIN reaper caught it. run_service now spends one shared
    # SEGMENT budget across every invoke in a task, and that budget is kept under
    # the soft limit by SEGMENT_BUDGET_MARGIN_SEC so the segment always fails
    # cleanly — persisting `failed` and an error message — inside its own task.
    TASK_SOFT_TIME_LIMIT_SEC: int = 600   # SIGTERM; task can still clean up
    TASK_TIME_LIMIT_SEC: int = 660        # SIGKILL if it ignored the above
    # Cap on a single graph invoke. The segment budget can shrink it further.
    LLM_STAGE_TIMEOUT_SEC: int = 300
    # Headroom left inside the soft limit for the non-LLM work in a segment
    # (evals, DB writes, checkpoint teardown) plus the failure path itself.
    SEGMENT_BUDGET_MARGIN_SEC: int = 60

    # Per-run LLM spend ceiling in USD. Once a run's accumulated cost (summed from
    # its run_costs rows plus the in-flight segment) reaches this, the reviewer
    # retry loop stops re-running the heavy research→analyse→review triad and the
    # graph ships what it has (graceful degrade) instead of burning up to the full
    # retry budget regardless of spend. On the free-tier default config every
    # routed model prices to ~$0, so this never trips there; it exists so a
    # paid-key deployment can't run away. Set to None or <= 0 to disable the
    # ceiling entirely (the retry cap of 3 still bounds the loop).
    RUN_COST_CEILING_USD: float | None = 1.0

    # Researcher pass budget. The first pass is deliberately shallow to fit Groq's
    # free 12K tokens/min ceiling (see agents/researcher.py). On a *retry* — which
    # only happens after the reviewer FAILed the prior pass — repeating that same
    # undersized pass just re-fails and re-bills it, so the budget escalates per
    # retry (more ReAct iterations + a larger synthesis reservation) to actually
    # act on the reviewer's feedback. Raise the base values on a paid key where the
    # per-minute ceiling isn't the binding constraint. (gap #3)
    RESEARCHER_MAX_ITER: int = 2
    RESEARCHER_MAX_TOKENS: int = 900
    RESEARCHER_RETRY_TOKEN_STEP: int = 500

    # Max characters of a *prior stage's* output re-fed as context into a later
    # stage's prompt (analysis→write reference, research→analyse reference, the
    # reviewer's retry feedback). Every stage is completion-capped, so these are
    # normally under budget and pass through untouched; this only bounds an
    # unusually large upstream output (big source docs, a verbose paid model) so
    # the re-sent context can't balloon a downstream call. (gap #4)
    CONTEXT_MAX_CHARS: int = 6000

    # Gemini embeddings for RAG.
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    EMBEDDING_DIMENSION: int = 384

    # Minimum cross-encoder score for a chunk to be shown to an agent. Retrieval
    # abstains ("No relevant documents found.") when nothing clears this, instead
    # of returning the top-5 of a uniformly irrelevant pool.
    #
    # cross-encoder/ms-marco-MiniLM-L-6-v2 emits unbounded raw logits, roughly
    # -11..+11, trained so a relevant query/passage pair lands above 0 and an
    # irrelevant one well below. 0.0 is therefore the model's own decision
    # boundary rather than a tuned constant — deliberately, since there is no
    # retrieval eval set to tune against yet. Raise it for stricter grounding,
    # lower it (negative) to loosen.
    RAG_MIN_RERANK_SCORE: float = 0.0

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
    # Shared HS256 signing key. The frontend mints tokens with it in
    # /api/backend-token; auth.py verifies them. Both sides must carry the SAME
    # value or every authenticated request 401s — see _validate_secret below.
    #
    # NEXTAUTH_SECRET is deliberately absent: it belongs to NextAuth in the
    # frontend and nothing here has ever read it. Declaring it required meant a
    # fresh clone refused to boot over a variable the backend does not use.
    BACKEND_JWT_SECRET: str
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

    # Persistent vector store for uploaded-document RAG. `vecs` is a thin
    # pgvector client (pgvector + psycopg2 + SQLAlchemy — no Supabase SDK), so
    # this is any Postgres with the vector extension, including the pgvector
    # image Compose already runs. Left unset it is derived from DATABASE_URL
    # below, which is why it has no separate entry in .env.example.
    #
    # It cannot simply reuse DATABASE_URL: that carries the +asyncpg driver for
    # SQLAlchemy's async engine, and vecs drives psycopg2 synchronously.
    VECTOR_DB_URL: str | None = None
    # Deprecated former name, still read so an existing .env keeps working.
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

# Older configs named this SUPABASE_DB_URL. Without this the value would be
# ignored and the derivation below would silently repoint the vector store at
# the local database — moving someone's embeddings out from under them.
if settings.SUPABASE_DB_URL and not settings.VECTOR_DB_URL:
    settings.VECTOR_DB_URL = settings.SUPABASE_DB_URL
    logger.warning("SUPABASE_DB_URL is deprecated — rename it to VECTOR_DB_URL")

# Derive the vecs DSN from the application database unless one is set
# explicitly. Runs AFTER the TESTING redirect above so the suite's vector
# collections land in the `_test` database alongside its tables, never in the
# real one. The only transform is dropping the async driver: DATABASE_URL is
# `postgresql+asyncpg://` for SQLAlchemy's async engine, while vecs uses
# psycopg2 and needs the bare `postgresql://` scheme.
if not settings.VECTOR_DB_URL:
    from sqlalchemy.engine import make_url

    # render_as_string(hide_password=False) — str(url) would mask the password.
    settings.VECTOR_DB_URL = (
        make_url(settings.DATABASE_URL)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )

_PROD_REQUIRED = ["TAVILY_API_KEY", "FIRECRAWL_API_KEY", "LLAMA_CLOUD_API_KEY"]

_FEATURE_LABEL = {
    "TAVILY_API_KEY": "web search",
    "FIRECRAWL_API_KEY": "web scraping",
    "LLAMA_CLOUD_API_KEY": "PDF parsing",
}


# The signing keys the repo ships. backend/.env.example, frontend/.env.local.example
# and docker-compose.yml all carry the same throwaway value on purpose, so that
# `cp backend/.env.example backend/.env && docker compose up` authenticates with
# no manual edits. Previously they disagreed, and the stack booted healthy while
# every authenticated request 401'd with nothing pointing at the cause.
#
# "test-secret" is CI's value; it is listed for the same reason.
_DEV_JWT_SECRETS = frozenset({
    "dummy-secret",
    "test-secret",
    "generate-with-openssl-rand-hex-32",
})

# `openssl rand -hex 32` is what every doc recommends; that is 64 chars. 32 is a
# floor, not a target — it only rejects values obviously too short for HS256.
_MIN_JWT_SECRET_LEN = 32


def _validate_secret(s: Settings) -> None:
    """Refuse to start production with a shipped or trivially weak signing key.

    Shipping a working default is what makes a fresh clone boot, but it is only
    safe if promoting that same file to production fails loudly: anyone holding
    this key can mint a token for any `sub` and impersonate any user.
    """
    if s.ENVIRONMENT != "production":
        return
    if s.BACKEND_JWT_SECRET in _DEV_JWT_SECRETS:
        raise RuntimeError(
            "BACKEND_JWT_SECRET is still a shipped development value. Generate "
            "one with `openssl rand -hex 32` and set it in BOTH the backend and "
            "frontend environments — they must match."
        )
    if len(s.BACKEND_JWT_SECRET) < _MIN_JWT_SECRET_LEN:
        raise RuntimeError(
            f"BACKEND_JWT_SECRET must be at least {_MIN_JWT_SECRET_LEN} "
            f"characters in production (got {len(s.BACKEND_JWT_SECRET)})."
        )


def _is_blank(value: str | None) -> bool:
    """Treat unset, empty, and whitespace-only as equally missing.

    These come from a `.env` file, where `TAVILY_API_KEY=` is a far more natural
    way to disable a key than deleting the line — and pydantic reads that as `""`,
    not `None`. An `is None` check let it through, so production booted clean and
    then failed on the first search call, which is exactly what the fail-fast is
    supposed to prevent.
    """
    return value is None or not value.strip()


def validate_config(s: Settings) -> None:
    _validate_secret(s)
    missing = [k for k in _PROD_REQUIRED if _is_blank(getattr(s, k))]
    # A blank URL must not exempt anything either: it would waive the key check
    # for a self-hosted backend that isn't actually configured.
    if not _is_blank(s.SEARXNG_URL):
        missing = [k for k in missing if k != "TAVILY_API_KEY"]
    if not _is_blank(s.FIRECRAWL_API_URL):
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
