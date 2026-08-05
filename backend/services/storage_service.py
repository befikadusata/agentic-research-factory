"""Durable storage for uploaded PDFs, shared by the API and the Celery worker.

Upload and ingestion are deliberately split: `POST /upload` returns `pending`
immediately and a Celery task parses the file later. That split means the two
halves are different processes, and under Compose different containers — so the
bytes have to land somewhere both can reach. A container-local path is not that
place, and using one broke uploaded-document RAG completely and silently: the
worker's open() raised ENOENT, `parse_pdf` caught it and returned no chunks, and
the document was recorded as having no extractable text.

The `s3` backend puts them in any S3-compatible object store — MinIO under
Compose, real S3/R2/Spaces when hosted — which is reachable over the network no
matter where either process runs. The `local` backend keeps the filesystem
behaviour for single-process runs and the test suite.

`file_path` on the Document row holds whichever locator the backend produced: an
`s3://bucket/key` URI, or an absolute path. Reading goes through `materialize`,
which dispatches on that prefix, so rows written by either backend stay readable.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

from config import settings
from logger import logger

_S3_PREFIX = "s3://"


class ObjectNotFound(Exception):
    """The document row points at bytes the store does not have.

    Distinct from a parse failure on purpose — the two need different messages.
    An unparseable PDF is the user's file; a missing object is our plumbing.
    """


def _client():
    """Build the S3 client lazily.

    Not at import: `local` deployments and most of the test suite never touch
    object storage, and botocore's session setup is not free. Cached on the
    function so repeated uploads reuse one connection pool.
    """
    if getattr(_client, "_cached", None) is None:
        import boto3
        from botocore.config import Config

        _client._cached = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT_URL or None,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY or None,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY or None,
            region_name=settings.STORAGE_REGION,
            # Path-style addressing: MinIO serves buckets as `host:9000/bucket`,
            # while the SDK default (virtual-host style) would try to resolve
            # `bucket.minio`, which has no DNS record inside Compose.
            config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
        )
    return _client._cached


def _ensure_bucket() -> None:
    """Create the bucket on first use if it isn't there.

    Cheaper than an `mc mb` init container in Compose, and it makes a fresh
    clone work with no setup step. On a real S3 account the bucket normally
    already exists, so this is one HEAD and nothing else.
    """
    if getattr(_ensure_bucket, "_done", False):
        return
    from botocore.exceptions import ClientError

    client = _client()
    try:
        client.head_bucket(Bucket=settings.STORAGE_BUCKET)
    except ClientError as e:
        # 403 means it exists and belongs to someone else — surface that rather
        # than attempting a create that will fail with a less obvious error.
        if e.response.get("Error", {}).get("Code") not in ("404", "NoSuchBucket"):
            raise
        client.create_bucket(Bucket=settings.STORAGE_BUCKET)
        logger.info("storage_bucket_created", bucket=settings.STORAGE_BUCKET)
    _ensure_bucket._done = True


def _put_sync(key: str, content: bytes) -> str:
    _ensure_bucket()
    _client().put_object(
        Bucket=settings.STORAGE_BUCKET,
        Key=key,
        Body=content,
        ContentType="application/pdf",
    )
    return f"{_S3_PREFIX}{settings.STORAGE_BUCKET}/{key}"


def _write_local_sync(path: str, content: bytes) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)
    return path


async def store_upload(doc_id: UUID, content: bytes) -> str:
    """Persist an uploaded PDF and return the locator to record on the row.

    Both backends run their blocking I/O on a worker thread — this is called
    from the request handler, and neither a disk write nor an S3 PUT belongs on
    the event loop.
    """
    key = f"{doc_id}.pdf"
    if settings.STORAGE_BACKEND == "s3":
        return await asyncio.to_thread(_put_sync, key, content)
    return await asyncio.to_thread(
        _write_local_sync, os.path.join(settings.UPLOAD_DIR, key), content
    )


def _download_sync(bucket: str, key: str, dest: str) -> None:
    from botocore.exceptions import ClientError

    try:
        _client().download_file(bucket, key, dest)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            raise ObjectNotFound(f"{_S3_PREFIX}{bucket}/{key}") from e
        raise


@asynccontextmanager
async def materialize(locator: str) -> AsyncIterator[str]:
    """Yield a local filesystem path for `locator` for the duration of the block.

    Docling and LlamaParse both take a path rather than a stream, so an object
    has to be staged on disk to be parsed. The staged copy is deleted on exit —
    the object store holds the durable copy, so nothing is lost and the worker's
    disk doesn't grow with every ingest. For the local backend the file *is* the
    durable copy, so it is yielded in place and left alone.

    Raises ObjectNotFound if the bytes are gone.
    """
    if not locator.startswith(_S3_PREFIX):
        if not os.path.exists(locator):
            raise ObjectNotFound(locator)
        yield locator
        return

    bucket, _, key = locator[len(_S3_PREFIX):].partition("/")
    fd, staged = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        await asyncio.to_thread(_download_sync, bucket, key, staged)
        yield staged
    finally:
        try:
            os.remove(staged)
        except OSError:
            logger.warning("storage_stage_cleanup_failed", path=staged)
