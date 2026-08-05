import asyncio
import html as html_lib
import os
import markdown
import weasyprint
from config import settings
from logger import logger
from utils.blocking import call_with_timeout

# Wall-clock cap on one docling parse. Docling's layout/OCR models are baked into
# the image (see backend/Dockerfile), so this bounds the parse itself rather than
# a first-run model download — a scanned or pathological PDF, not a cold start.
PDF_PARSE_TIMEOUT_SEC = 120


async def markdown_to_pdf(
    md_content: str,
    output_path: str,
    *,
    title: str = "",
    generated_at: str = "",
) -> str:
    """Convert markdown string to PDF file. Returns the output path."""
    body_html = markdown.markdown(md_content, extensions=["tables", "fenced_code"])
    header_html = ""
    if title or generated_at:
        escaped_title = html_lib.escape(title)
        header_html = (
            f'<div class="report-header">'
            f'<h1 class="report-title">{escaped_title}</h1>'
            f'<p class="report-date">Generated: {html_lib.escape(generated_at)}</p>'
            f"</div><hr>"
        )
    styled_html = f"""<html><head><style>
      body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto;
              line-height: 1.6; color: #333; }}
      .report-header {{ margin-bottom: 24px; }}
      .report-title {{ font-size: 1.6em; color: #1a1a2e; margin: 0 0 4px; border: none; padding: 0; }}
      .report-date {{ font-size: 0.85em; color: #777; margin: 0; }}
      hr {{ border: none; border-top: 2px solid #534AB7; margin: 16px 0 24px; }}
      h1 {{ color: #1a1a2e; border-bottom: 2px solid #534AB7; padding-bottom: 8px; }}
      h2 {{ color: #333; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
      table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
      th {{ background: #534AB7; color: white; padding: 8px 12px; }}
      td {{ border: 1px solid #ddd; padding: 8px 12px; }}
      blockquote {{ border-left: 4px solid #534AB7; margin: 0; padding-left: 16px; color: #555; }}
      code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
      pre {{ white-space: pre-wrap; overflow-wrap: break-word; font-size: 0.85em;
             background: #f4f4f4; padding: 12px; border-radius: 4px; }}
    </style></head><body>{header_html}{body_html}</body></html>"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: weasyprint.HTML(string=styled_html).write_pdf(output_path))
    return output_path


def _build_converter():
    """A DocumentConverter pinned to what this image can actually run.

    Two deliberate departures from docling's defaults, both of which otherwise
    fail at parse time and get swallowed into an empty (silent) ingest:

    * layout_options pins DOCLING_LAYOUT_V2. The default spec is
      docling-layout-heron, an RT-DETRv2 checkpoint that the locked
      transformers 4.46.3 cannot load ("does not recognize this architecture").
      Pinning the older layout model is the surgical fix; bumping transformers
      would re-resolve the lock, which the Dockerfile documents as dragging
      crewai to a version that breaks Pydantic tool-schema generation.
    * do_ocr=False. OCR would need an engine resolved through OcrAutoOptions,
      which reports "No OCR engine found" in this image, and it is dead weight
      for the text-bearing PDFs this app ingests. Consequence: a scanned or
      image-only PDF yields no text, which ingest_service records as `failed`.

    Models are baked into the image and located via DOCLING_ARTIFACTS_PATH, so
    this constructor does no network I/O.
    """
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, LayoutOptions
    from docling.datamodel.layout_model_specs import DOCLING_LAYOUT_V2

    opts = PdfPipelineOptions()
    opts.do_ocr = False
    opts.layout_options = LayoutOptions(model_spec=DOCLING_LAYOUT_V2)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def _parse_with_docling(path: str) -> list[dict]:
    """Chunk a PDF page by page, so every chunk carries the page it came from.

    A whole-document `export_to_markdown()` flattens away docling's provenance
    and leaves `"page": None` on every chunk. Exporting one page at a time keeps
    the markdown structure the splitter needs and gives each chunk a real page
    number.

    Deliberate consequence: chunks never straddle a page break, so a page's tail
    is a short chunk with no overlap across the boundary. A chunk spanning two
    pages could only be labelled with one of them, and a citation pointing at the
    wrong page is worse than a slightly smaller chunk.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    converter = _build_converter()
    result = converter.convert(path)
    document = result.document

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    filename = os.path.basename(path)

    chunks: list[dict] = []
    for page_no in sorted(getattr(document, "pages", None) or {}):
        page_md = document.export_to_markdown(page_no=page_no)
        if not page_md.strip():
            continue
        chunks.extend(
            {"text": chunk, "metadata": {"source": filename, "page": page_no}}
            for chunk in splitter.split_text(page_md)
        )
    if chunks:
        return chunks

    # No page provenance (docling populates `pages` per backend, and some inputs
    # yield none). Better to ingest without page numbers than not at all.
    md_text = document.export_to_markdown()
    if not md_text.strip():
        return []
    logger.info("docling_parse_without_page_provenance", path=path)
    return [
        {"text": chunk, "metadata": {"source": filename, "page": None}}
        for chunk in splitter.split_text(md_text)
    ]


async def _parse_with_llamaparse(paths: list[str]) -> list[dict]:
    from llama_parse import LlamaParse
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from config import settings

    parser = LlamaParse(api_key=settings.LLAMA_CLOUD_API_KEY, result_type="markdown")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = []
    for path in paths:
        filename = os.path.basename(path)
        docs = await parser.aload_data(path)
        for doc in docs:
            for chunk_text in splitter.split_text(doc.text):
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": filename,
                        "page": doc.metadata.get("page_number") if hasattr(doc, "metadata") else None,
                    }
                })
    return chunks


async def parse_pdf(path: str) -> list[dict]:
    """Parse a single PDF. Docling primary, LlamaParse fallback."""
    try:
        # call_with_timeout, NOT run_in_executor(None, ...): the default executor's
        # threads are joined by asyncio.run() at task teardown, so a docling parse
        # that blew this timeout would keep running and wedge the Celery worker
        # child until it finished anyway.
        chunks = await call_with_timeout(
            _parse_with_docling, path,
            timeout=PDF_PARSE_TIMEOUT_SEC,
            name="docling-parse",
        )
        if chunks:
            return chunks
    except Exception as e:
        # TimeoutError stringifies to "", hence the type-name fallback.
        logger.warning("docling_parse_failed", path=path, error=str(e) or type(e).__name__)

    if settings.LLAMA_CLOUD_API_KEY:
        try:
            return await _parse_with_llamaparse([path])
        except Exception as e:
            logger.warning("llamaparse_fallback_failed", path=path, error=str(e))

    return []


async def parse_pdfs(paths: list[str]) -> list[dict]:
    """Parse multiple PDFs — thin loop over parse_pdf for backward compat."""
    chunks = []
    for path in paths:
        chunks.extend(await parse_pdf(path))
    return chunks
