import asyncio
import html as html_lib
import os
import markdown
import weasyprint
from config import settings
from logger import logger


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


def _parse_with_docling(path: str) -> list[dict]:
    from docling.document_converter import DocumentConverter
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    converter = DocumentConverter()
    result = converter.convert(path)
    md_text = result.document.export_to_markdown()
    if not md_text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    filename = os.path.basename(path)
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
    loop = asyncio.get_event_loop()
    try:
        chunks = await loop.run_in_executor(None, _parse_with_docling, path)
        if chunks:
            return chunks
    except Exception as e:
        logger.warning("docling_parse_failed", path=path, error=str(e))

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
