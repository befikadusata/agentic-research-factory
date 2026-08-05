from uuid import UUID
from database import AsyncSessionLocal
from models import Document, DocumentStatus
from services.pdf_service import parse_pdf
from services.storage_service import ObjectNotFound, materialize
from tools.rag import ingest_documents
from logger import logger


async def ingest_doc(doc_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return
        try:
            # Staged to a local path only for the parse — see storage_service.
            async with materialize(doc.file_path) as path:
                chunks = await parse_pdf(path)
            doc.chunk_count = len(chunks)
            if chunks:
                ingest_documents(chunks, collection_name=f"workspace_{doc.workspace_id}", vertical=doc.vertical)
                doc.status = DocumentStatus.ready
                logger.info("ingest_complete", doc_id=str(doc_id), chunks=len(chunks))
            else:
                # parse_pdf swallows every parser failure and returns []. Marking
                # that `ready` would tell the UI the upload succeeded while nothing
                # was embedded, so every later run would silently have no document
                # context. Fail it so the operator — and _run_start_segment's
                # ingestion check — sees it.
                doc.status = DocumentStatus.failed
                doc.error_message = (
                    "No text could be extracted from this PDF. It may be empty, "
                    "image-only, or too large to parse within the time limit."
                )
                logger.warning("ingest_no_chunks", doc_id=str(doc_id))
        except ObjectNotFound:
            # Caught ahead of the blanket handler because the generic parser
            # message above is misleading here: the PDF is fine, we just cannot
            # see it. A container-local UPLOAD_DIR produces this on every upload
            # once the API and the worker stop sharing a filesystem.
            doc.status = DocumentStatus.failed
            doc.error_message = (
                "The uploaded file is no longer in storage, so it could not be "
                "parsed. Re-upload the document. If this happens to every "
                "upload, the API and the worker are not reading the same "
                "storage — check STORAGE_BACKEND."
            )
            logger.warning(
                "ingest_object_missing", doc_id=str(doc_id), locator=doc.file_path
            )
        except Exception as e:
            doc.status = DocumentStatus.failed
            doc.error_message = str(e)[:500]
            logger.warning("ingest_failed", doc_id=str(doc_id), error=str(e))
        await db.commit()
