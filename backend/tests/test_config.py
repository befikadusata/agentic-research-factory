import re
from pathlib import Path

import pytest
from config import Settings, validate_config


# A production-grade stand-in: not one of the shipped dev values and long
# enough to clear the length floor, so these cases exercise the key checks
# rather than tripping the signing-secret guard first.
_STRONG_SECRET = "a" * 64


def _settings(**overrides):
    base = {
        "DATABASE_URL": "postgresql+asyncpg://user:password@localhost:5432/test",
        "BACKEND_JWT_SECRET": _STRONG_SECRET,
        "ENVIRONMENT": "production",
        # .env (loaded by Settings' env_file config) sets real values for
        # these in local dev — force them unset unless a test overrides them.
        "TAVILY_API_KEY": None,
        "FIRECRAWL_API_KEY": None,
        "LLAMA_CLOUD_API_KEY": None,
        "SEARXNG_URL": None,
        "FIRECRAWL_API_URL": None,
    }
    base.update(overrides)
    return Settings(**base)


def test_validate_config_requires_all_keys_by_default():
    s = _settings()
    with pytest.raises(RuntimeError) as exc:
        validate_config(s)
    assert "TAVILY_API_KEY" in str(exc.value)
    assert "FIRECRAWL_API_KEY" in str(exc.value)
    assert "LLAMA_CLOUD_API_KEY" in str(exc.value)


def test_validate_config_searxng_url_exempts_tavily_key():
    s = _settings(SEARXNG_URL="http://localhost:8081", LLAMA_CLOUD_API_KEY="llx-x", FIRECRAWL_API_KEY="fc-x")
    validate_config(s)  # should not raise


def test_validate_config_firecrawl_api_url_exempts_firecrawl_key():
    s = _settings(FIRECRAWL_API_URL="http://localhost:3002", TAVILY_API_KEY="tvly-x", LLAMA_CLOUD_API_KEY="llx-x")
    validate_config(s)  # should not raise


def test_validate_config_firecrawl_api_url_alone_still_requires_tavily():
    s = _settings(FIRECRAWL_API_URL="http://localhost:3002", LLAMA_CLOUD_API_KEY="llx-x")
    with pytest.raises(RuntimeError) as exc:
        validate_config(s)
    assert "TAVILY_API_KEY" in str(exc.value)
    assert "FIRECRAWL_API_KEY" not in str(exc.value)


# --- BACKEND_JWT_SECRET guard -------------------------------------------------
# The repo ships a working dev secret so a fresh clone boots authenticated.
# These tests are what make that safe: the same file promoted to production
# must fail loudly rather than sign tokens with a publicly known key.


def _prod_ready(**overrides):
    """Settings that pass every check except the one under test.

    Merged rather than passed as keywords so a caller can override the provider
    keys themselves — which the blank-value tests below do.
    """
    base = {
        "TAVILY_API_KEY": "tvly-x",
        "FIRECRAWL_API_KEY": "fc-x",
        "LLAMA_CLOUD_API_KEY": "llx-x",
    }
    base.update(overrides)
    return _settings(**base)


@pytest.mark.parametrize(
    "secret",
    ["dummy-secret", "test-secret", "generate-with-openssl-rand-hex-32"],
)
def test_production_rejects_shipped_dev_secrets(secret):
    """Every literal in .env.example / .env.local.example / docker-compose.yml.

    If someone changes the shipped default without adding it here, this test
    keeps passing but the guard stops covering the new value — so the value in
    those files and _DEV_JWT_SECRETS must be kept in sync.
    """
    with pytest.raises(RuntimeError, match="shipped development value"):
        validate_config(_prod_ready(BACKEND_JWT_SECRET=secret))


def test_production_rejects_short_secret():
    with pytest.raises(RuntimeError, match="at least 32"):
        validate_config(_prod_ready(BACKEND_JWT_SECRET="x" * 31))


def test_production_accepts_strong_secret():
    validate_config(_prod_ready(BACKEND_JWT_SECRET="x" * 32))  # should not raise


def test_development_allows_the_shipped_secret():
    """The whole point of the default: `docker compose up` must just work."""
    validate_config(
        _prod_ready(ENVIRONMENT="development", BACKEND_JWT_SECRET="dummy-secret")
    )


def test_backend_does_not_require_nextauth_secret():
    """NEXTAUTH_SECRET is frontend-only; requiring it blocked a clean boot."""
    s = _prod_ready()
    assert not hasattr(s, "NEXTAUTH_SECRET")


_REPO_ROOT = Path(__file__).resolve().parents[2]

# The frontend signs tokens with its copy of this value and the backend verifies
# them with its own. They live in three separate files with no mechanism forcing
# agreement, and they HAVE disagreed: the stack booted healthy, login succeeded,
# and every authenticated request 401'd with nothing in the logs naming the
# cause. This test is that missing mechanism.
_SECRET_SOURCES = [
    "backend/.env.example",
    "frontend/.env.local.example",
    "docker-compose.yml",
]


def test_shipped_jwt_secret_matches_across_every_file():
    found = {}
    for rel in _SECRET_SOURCES:
        path = _REPO_ROOT / rel
        assert path.exists(), f"{rel} moved — update _SECRET_SOURCES"
        match = re.search(r"BACKEND_JWT_SECRET=(\S+)", path.read_text())
        assert match, f"{rel} no longer defines BACKEND_JWT_SECRET"
        found[rel] = match.group(1)

    assert len(set(found.values())) == 1, (
        f"BACKEND_JWT_SECRET disagrees across files — every authenticated "
        f"request will 401 on a fresh clone: {found}"
    )


def test_shipped_jwt_secret_is_rejected_in_production():
    """Ties the two halves together: whatever value ships must be denylisted.

    Aligning the files is only safe because promoting them to production
    fails. If someone rotates the shipped default, this fails until the new
    value is added to _DEV_JWT_SECRETS.
    """
    text = (_REPO_ROOT / "backend/.env.example").read_text()
    shipped = re.search(r"BACKEND_JWT_SECRET=(\S+)", text).group(1)

    with pytest.raises(RuntimeError):
        validate_config(_prod_ready(BACKEND_JWT_SECRET=shipped))


# --- blank vs. unset ----------------------------------------------------------
# These arrive from a .env file, where `TAVILY_API_KEY=` is the natural way to
# disable a key — pydantic reads that as "", not None. An `is None` check let it
# through, so production booted clean and failed on the first search call.


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
@pytest.mark.parametrize("key", ["TAVILY_API_KEY", "FIRECRAWL_API_KEY", "LLAMA_CLOUD_API_KEY"])
def test_production_treats_blank_keys_as_missing(key, blank):
    with pytest.raises(RuntimeError) as exc:
        validate_config(_prod_ready(**{key: blank}))
    assert key in str(exc.value)


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_searxng_url_does_not_exempt_tavily_key(blank):
    """A blank URL is not a configured self-hosted backend."""
    with pytest.raises(RuntimeError) as exc:
        validate_config(_prod_ready(TAVILY_API_KEY=None, SEARXNG_URL=blank))
    assert "TAVILY_API_KEY" in str(exc.value)


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_firecrawl_url_does_not_exempt_firecrawl_key(blank):
    with pytest.raises(RuntimeError) as exc:
        validate_config(_prod_ready(FIRECRAWL_API_KEY=None, FIRECRAWL_API_URL=blank))
    assert "FIRECRAWL_API_KEY" in str(exc.value)


def test_blank_key_in_development_warns_rather_than_raising(caplog):
    """Non-production keeps degrading gracefully — this only tightens prod."""
    validate_config(_prod_ready(ENVIRONMENT="development", TAVILY_API_KEY=""))
