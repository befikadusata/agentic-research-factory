from uuid import UUID
from database import AsyncSessionLocal
from models import Document, DocumentStatus
from services.pdf_service import parse_pdf
from tools.rag import ingest_documents
from logger import logger


async def ingest_doc(doc_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return
        try:
            chunks = await parse_pdf(doc.file_path)
            if chunks:
                ingest_documents(chunks, collection_name=f"workspace_{doc.workspace_id}", vertical=doc.vertical)
            doc.status = DocumentStatus.ready
            doc.chunk_count = len(chunks)
            logger.info("ingest_complete", doc_id=str(doc_id), chunks=len(chunks))
        except Exception as e:
            doc.status = DocumentStatus.failed
            doc.error_message = str(e)[:500]
            logger.warning("ingest_failed", doc_id=str(doc_id), error=str(e))
        await db.commit()
