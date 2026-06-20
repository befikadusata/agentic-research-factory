import asyncio
import markdown
import weasyprint

async def markdown_to_pdf(md_content: str, output_path: str) -> str:
    """Convert markdown string to PDF file. Returns the output path."""
    html = markdown.markdown(md_content, extensions=["tables", "fenced_code"])
    styled_html = f"""<html><head><style>
      body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto;
              line-height: 1.6; color: #333; }}
      h1 {{ color: #1a1a2e; border-bottom: 2px solid #534AB7; padding-bottom: 8px; }}
      h2 {{ color: #333; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
      table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
      th {{ background: #534AB7; color: white; padding: 8px 12px; }}
      td {{ border: 1px solid #ddd; padding: 8px 12px; }}
      blockquote {{ border-left: 4px solid #534AB7; margin: 0; padding-left: 16px; color: #555; }}
      code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
    </style></head><body>{html}</body></html>"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: weasyprint.HTML(string=styled_html).write_pdf(output_path))
    return output_path

async def parse_pdfs(paths: list[str]) -> list[dict]:
    """Parse uploaded PDFs into text chunks with metadata using LlamaParse."""
    try:
        from llama_parse import LlamaParse
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from config import settings
        import os
        parser = LlamaParse(api_key=settings.LLAMA_CLOUD_API_KEY, result_type="markdown")
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        chunks = []
        for path in paths:
            filename = os.path.basename(path)
            docs = await parser.aload_data(path)
            for doc in docs:
                split_texts = splitter.split_text(doc.text)
                for chunk_text in split_texts:
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {
                            "source": filename,
                            "page": doc.metadata.get("page_number") if hasattr(doc, "metadata") else None
                        }
                    })
        return chunks
    except Exception as e:
        print(f"PDF parse error: {e}")
        return []
