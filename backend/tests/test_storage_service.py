"""Uploaded-PDF storage.

The bug these cover: upload (API) and ingestion (Celery worker) are separate
processes, and writing to a container-local path meant the worker never found
the file. Every upload then failed as "no text could be extracted" — the PDF was
fine, the two halves just weren't looking at the same bytes. So the round-trip
that matters is store-here / read-there, not either half alone.
"""

import os
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from config import settings
from services import storage_service
from services.storage_service import ObjectNotFound, materialize, store_upload


@pytest.fixture(autouse=True)
def _reset_storage_caches():
    """Drop the memoised client and bucket check between tests.

    Both are cached on the function object for the life of the process, so
    without this a stub client would leak into the next test.
    """
    storage_service._client._cached = None
    storage_service._ensure_bucket._done = False
    yield
    storage_service._client._cached = None
    storage_service._ensure_bucket._done = False


@pytest.fixture
def local_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    return tmp_path


@pytest.fixture
def s3_backend(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "STORAGE_BUCKET", "test-bucket")
    client = MagicMock()
    storage_service._client._cached = client
    storage_service._ensure_bucket._done = True
    return client


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code}}, "op")


@pytest.mark.asyncio
async def test_local_store_writes_bytes_and_returns_path(local_backend):
    doc_id = uuid4()
    path = await store_upload(doc_id, b"%PDF-1.7 body")

    assert path == os.path.join(settings.UPLOAD_DIR, f"{doc_id}.pdf")
    with open(path, "rb") as f:
        assert f.read() == b"%PDF-1.7 body"


@pytest.mark.asyncio
async def test_local_store_creates_upload_dir(local_backend):
    """Storing has to create UPLOAD_DIR itself rather than relying on the router
    to do it at import time, or the first upload after a fresh boot fails."""
    assert not os.path.exists(settings.UPLOAD_DIR)
    await store_upload(uuid4(), b"%PDF")
    assert os.path.isdir(settings.UPLOAD_DIR)


@pytest.mark.asyncio
async def test_local_materialize_yields_in_place_and_keeps_file(local_backend):
    """For the local backend the file IS the durable copy — materialize must not
    stage a second one, and must not delete the original on exit."""
    path = await store_upload(uuid4(), b"%PDF")
    async with materialize(path) as staged:
        assert staged == path
    assert os.path.exists(path)


@pytest.mark.asyncio
async def test_local_materialize_raises_when_file_is_gone(local_backend):
    with pytest.raises(ObjectNotFound):
        async with materialize(str(local_backend / "never-written.pdf")):
            pass


@pytest.mark.asyncio
async def test_s3_store_puts_object_and_returns_uri(s3_backend):
    doc_id = uuid4()
    uri = await store_upload(doc_id, b"%PDF-1.7 body")

    assert uri == f"s3://test-bucket/{doc_id}.pdf"
    s3_backend.put_object.assert_called_once()
    kwargs = s3_backend.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Key"] == f"{doc_id}.pdf"
    assert kwargs["Body"] == b"%PDF-1.7 body"


@pytest.mark.asyncio
async def test_s3_materialize_stages_locally_then_cleans_up(s3_backend):
    def _fake_download(bucket, key, dest):
        with open(dest, "wb") as f:
            f.write(b"%PDF staged")

    s3_backend.download_file.side_effect = _fake_download

    async with materialize("s3://test-bucket/abc.pdf") as staged:
        assert os.path.exists(staged)
        with open(staged, "rb") as f:
            assert f.read() == b"%PDF staged"
        staged_path = staged

    # The object store holds the durable copy; the worker's disk must not grow
    # by one PDF per ingest.
    assert not os.path.exists(staged_path)
    s3_backend.download_file.assert_called_once_with("test-bucket", "abc.pdf", staged_path)


@pytest.mark.asyncio
async def test_s3_materialize_cleans_up_when_the_parse_raises(s3_backend):
    s3_backend.download_file.side_effect = lambda b, k, dest: open(dest, "wb").close()

    staged_path = None
    with pytest.raises(RuntimeError):
        async with materialize("s3://test-bucket/abc.pdf") as staged:
            staged_path = staged
            raise RuntimeError("docling exploded")

    assert staged_path and not os.path.exists(staged_path)


@pytest.mark.asyncio
async def test_s3_materialize_raises_object_not_found_on_missing_key(s3_backend):
    s3_backend.download_file.side_effect = _client_error("NoSuchKey")

    with pytest.raises(ObjectNotFound):
        async with materialize("s3://test-bucket/gone.pdf"):
            pass


@pytest.mark.asyncio
async def test_s3_materialize_propagates_other_client_errors(s3_backend):
    """A credentials or connectivity failure is not a missing object, and must
    not be reported to the operator as one."""
    s3_backend.download_file.side_effect = _client_error("AccessDenied")

    with pytest.raises(ClientError):
        async with materialize("s3://test-bucket/x.pdf"):
            pass


@pytest.mark.asyncio
async def test_bucket_is_created_when_absent(monkeypatch):
    """A fresh MinIO volume has no buckets, so the first upload has to make one
    rather than requiring a manual setup step."""
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "STORAGE_BUCKET", "new-bucket")
    client = MagicMock()
    client.head_bucket.side_effect = _client_error("404")
    storage_service._client._cached = client

    await store_upload(uuid4(), b"%PDF")

    client.create_bucket.assert_called_once_with(Bucket="new-bucket")


@pytest.mark.asyncio
async def test_existing_bucket_is_not_recreated(s3_backend):
    await store_upload(uuid4(), b"%PDF")
    s3_backend.create_bucket.assert_not_called()


@pytest.mark.asyncio
async def test_bucket_check_propagates_permission_error(monkeypatch):
    """403 means the bucket exists and belongs to someone else. Attempting a
    create there produces a far less obvious error than surfacing this one."""
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    client = MagicMock()
    client.head_bucket.side_effect = _client_error("403")
    storage_service._client._cached = client

    with pytest.raises(ClientError):
        await store_upload(uuid4(), b"%PDF")
    client.create_bucket.assert_not_called()


def test_unrecognised_storage_backend_is_rejected():
    """A typo silently selecting local storage is the exact failure mode this
    setting exists to prevent, so it must not be reachable."""
    from config import Settings, _validate_storage

    with pytest.raises(RuntimeError, match="STORAGE_BACKEND"):
        _validate_storage(Settings(STORAGE_BACKEND="S3"))
