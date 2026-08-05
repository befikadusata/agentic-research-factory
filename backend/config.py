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
    # via llm_router.MODEL_REGISTRY / ROLE_CAPS, which picks the cheapest model fit
    # for the role from whichever providers have keys, and works on a single
    # provider (Groq 8B for light work, Groq 70B for reasoning/writing/judging).
    # Setting one pins that agent to a specific slug and wins over routing; the
    # `openrouter/` prefix must be explicit so litellm routes it correctly.
    #
    # OpenRouter's free Tencent hy3 is a reasoning model that returns empty
    # `content` under real crewai load (fails the stage), so it is NOT a routed
    # primary — it stays only as the cross-provider fallback slug and for pricing
    # (see services/llm_router.py).
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
    # distinct model in BOTH legacy and routed mode (legacy mode otherwise
    # collapses every agent onto the single LLM_MODEL). Unset → judges follow the
    # normal resolution (legacy: LLM_MODEL; routed: REVIEWER_MODEL/EVAL_MODEL).
    # A different model on the same provider is enough to break the shared blind
    # spot; it does not need a second provider key.
    JUDGE_MODEL: str | None = None

    # A run stuck in a non-terminal state (pending / researching / analyzing /
    # writing, or an *autonomous* run parked at an approval gate) longer than
    # this — with no segment task advancing it — is considered orphaned and
    # reaped to `failed` by the beat-driven reaper. Must exceed the Celery hard
    # task limit (~11 min) plus a margin, so a still-running segment is never
    # mistaken for a dead one.
    RUN_STUCK_TIMEOUT_MIN: int = 20

    # Celery per-task limits, and the LLM budget derived from them. run_service
    # spends one shared SEGMENT budget across every invoke in a task, and
    # SEGMENT_BUDGET_MARGIN_SEC keeps that budget under the soft limit so a slow
    # segment fails cleanly inside its own task — persisting `failed` and an error
    # message — instead of being killed mid-flight and left non-terminal.
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
    # graph ships what it has. On the free-tier default config every routed model
    # prices to ~$0, so this only ever trips a paid-key deployment. Set to None or
    # <= 0 to disable the ceiling (the retry cap of 3 still bounds the loop).
    RUN_COST_CEILING_USD: float | None = 1.0

    # Researcher pass budget. The first pass is deliberately shallow to fit Groq's
    # free 12K tokens/min ceiling (see agents/researcher.py). On a *retry* — which
    # only happens after the reviewer FAILed the prior pass — repeating that same
    # undersized pass just re-fails and re-bills it, so the budget escalates per
    # retry (more ReAct iterations + a larger synthesis reservation) to actually
    # act on the reviewer's feedback. Raise the base values on a paid key where the
    # per-minute ceiling isn't the binding constraint.
    RESEARCHER_MAX_ITER: int = 2
    RESEARCHER_MAX_TOKENS: int = 900
    RESEARCHER_RETRY_TOKEN_STEP: int = 500

    # Max characters of a *prior stage's* output re-fed as context into a later
    # stage's prompt (analysis→write reference, research→analyse reference, the
    # reviewer's retry feedback). Every stage is completion-capped, so these are
    # normally under budget and pass through untouched; this only bounds an
    # unusually large upstream output (big source docs, a verbose paid model) so
    # the re-sent context can't balloon a downstream call.
    CONTEXT_MAX_CHARS: int = 6000

    # Gemini embeddings for RAG.
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    EMBEDDING_DIMENSION: int = 384

    # Cache embedding vectors in Redis, keyed by (provider, model, dimension,
    # text). Off under pytest — a shared cache would make "did this call the
    # embedder?" assertions depend on what an earlier test happened to warm, and
    # the cache has its own tests that enable it explicitly.
    EMBEDDING_CACHE_ENABLED: bool = True

    # How many chunks either side of a retrieved chunk to hand the agent with it.
    #
    # Retrieval ranks 1000-character windows because that is what the embedder and
    # the re-ranker can read in full (see docs/optimizations.md), but 1000
    # characters is not a unit of meaning: the window that scores highest is
    # regularly the one that names the thing, while the sentence qualifying it sits
    # in the next window and never reaches the agent.
    #
    # Expansion never crosses a page boundary, so the citation stays exact — see
    # tools/rag.expand_context. 0 disables it and restores chunk-at-a-time output.
    RAG_NEIGHBOUR_RADIUS: int = 1

    # Score the best-reranked chunk must reach before retrieval answers at all.
    # Below it, RAGTool abstains and tells the agent to use web search instead.
    #
    # Measured by backend/evals/retrieval_eval.py running the real pipeline over a
    # real corpus. It must be set from those best-of-pool numbers, not from the
    # isolated (query, passage) scores backend/evals/rerank_calibration.py
    # produces: the gate compares against the best chunk retrieval can find
    # anywhere in the corpus, and best-of-pool scores sit well above pair scores,
    # so a threshold taken from pair scores lands far too low to gate anything.
    #
    # Best-chunk score over 62 answerable and 10 unanswerable queries:
    #
    #   answerable    min -11.161  median  +2.063  max +10.314
    #   unanswerable  min -11.231  median -10.256  max  -7.589
    #
    #   threshold   abstains on answerable   admits unanswerable
    #     -11.0            1/62                     9/10
    #      -9.0            1/62                     3/10
    #      -8.5            1/62                     1/10
    #      -7.5            7/62                     0/10
    #
    # -9.0 rather than the tighter -8.5: the lowest answerable query that still
    # passes scores -8.351, so -8.5 would sit 0.15 from a real answer and is tuned
    # to this corpus rather than robust to the next one. -9.0 keeps 0.65 of
    # headroom, and false abstentions do not start climbing until -8.0.
    #
    # The three unanswerable queries -9.0 still admits are company-financial
    # questions against a corpus full of company financials. Relevant and
    # same-topic-but-wrong overlap almost entirely, so no absolute threshold
    # separates "answers the question" from "is about the same subject". The gate
    # catches "these documents are not about this at all" and nothing finer;
    # ordering, not thresholding, selects among the chunks that clear it.
    RAG_MIN_RERANK_SCORE: float = -9.0

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
    # frontend and nothing here reads it, so declaring it required would stop a
    # fresh clone booting over a variable the backend does not use.
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

    # Where an uploaded PDF lives between the API that receives it and the
    # Celery worker that parses it. Those are separate processes — separate
    # containers under Compose — so "local" is only correct when both share a
    # filesystem. They don't by default, and when they don't the worker's open()
    # raises ENOENT, parse_pdf swallows it, and the document is recorded as having
    # no extractable text.
    #
    # "s3" is any S3-compatible object store — the MinIO service Compose runs,
    # or real S3/R2/Spaces in a hosted deployment — which both processes reach
    # over the network regardless of where they run.
    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = "/tmp/research_factory_uploads"
    STORAGE_BUCKET: str = "research-factory-uploads"
    # Unset → the AWS SDK's own endpoint resolution, i.e. real S3.
    STORAGE_ENDPOINT_URL: str | None = None
    STORAGE_ACCESS_KEY: str | None = None
    STORAGE_SECRET_KEY: str | None = None
    STORAGE_REGION: str = "us-east-1"

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
    settings.EMBEDDING_CACHE_ENABLED = False
    # The suite must never reach a real object store, and a developer whose .env
    # points at one would otherwise have their bucket written to by every upload
    # test. Tests that exercise the s3 path set this themselves.
    settings.STORAGE_BACKEND = "local"

# Older configs named this SUPABASE_DB_URL. Without this the value is ignored and
# the derivation below silently repoints the vector store at the local database —
# moving someone's embeddings out from under them.
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
# no manual edits. When they disagree the stack boots healthy and every
# authenticated request 401s with nothing pointing at the cause.
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
    not `None`. An `is None` check lets it through, so production boots clean and
    then fails on the first search call.
    """
    return value is None or not value.strip()


_STORAGE_BACKENDS = frozenset({"local", "s3"})


def _validate_storage(s: Settings) -> None:
    """Reject a storage setting that would fail only at upload time.

    An unrecognised value silently selects local storage, so uploads land in a
    filesystem the worker cannot see and the failure surfaces much later as "no
    text could be extracted" from a PDF that parses fine.
    """
    if s.STORAGE_BACKEND not in _STORAGE_BACKENDS:
        raise RuntimeError(
            f"STORAGE_BACKEND must be one of {sorted(_STORAGE_BACKENDS)} "
            f"(got {s.STORAGE_BACKEND!r})."
        )
    if s.STORAGE_BACKEND == "local":
        # Not fatal: a single-process deployment, and the test suite, are both
        # legitimately served by the local filesystem. It is only wrong when the
        # API and the worker are separate — which is the normal deployment.
        logger.warning(
            "STORAGE_BACKEND=local — uploaded PDFs are written to UPLOAD_DIR on "
            "the local filesystem. Uploaded-document RAG will fail unless the "
            "API and the Celery worker share it. Set STORAGE_BACKEND=s3 to use "
            "object storage instead."
        )


def validate_config(s: Settings) -> None:
    _validate_secret(s)
    _validate_storage(s)
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
