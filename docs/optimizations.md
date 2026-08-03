# Agentic Research Factory: Technical Optimizations & Features

This document outlines the architectural and functional optimizations implemented to prepare the Agentic Research Factory for production-grade workloads, focusing on scalability, observability, and high-precision RAG retrieval.

## 1. Production Scalability
- **Async Task Orchestration**: Migrated synchronous agent execution to `Celery` with a `Redis` broker and backend.
- **Task Delegation**: Refactored `routers/runs.py` to offload agent run tasks (`execute_run_task`), preventing API request timeouts and enabling horizontal scaling of worker nodes.

## 2. Observability & Monitoring
- **Performance Metrics**: Integrated `prometheus-fastapi-instrumentator` to expose system health and throughput at `/metrics`.
- **Granular Cost Tracking**: Implemented `RunCost` model to capture token usage and costs per agent run, enabling data-driven budget management and optimization of LLM utilization.

## 3. High-Precision RAG Pipeline
Optimized the retrieval augmented generation pipeline for both recall and precision:

### Chunking Strategy
`pdf_service.py` splits with `RecursiveCharacterTextSplitter` at `chunk_size=1000`, `chunk_overlap=200` **characters**, one page at a time.

- **Why recursive rather than fixed-width**: the splitter tries paragraph → line → sentence → word boundaries in order and cuts at the largest one that still fits. Docling emits Markdown, so those boundaries are real document structure rather than guesses, and a chunk rarely ends mid-sentence.
- **Why 1000 characters, not the usual "500 tokens"**: the number is set by the encoders, not by taste. 1000 characters is roughly 250 tokens. The local embedder `all-MiniLM-L6-v2` has a 256-token maximum sequence length and silently truncates beyond it, and the re-ranker `ms-marco-MiniLM-L-6-v2` scores each (query, passage) pair inside a 512-token window. A 500-*token* chunk would have its tail dropped from its own embedding and be truncated again during re-ranking — the pipeline would rank and return text that neither model ever fully read. 1000 characters is about the largest chunk both models still see in full.
- **Why 200 characters of overlap**: roughly two sentences. A fact whose subject sits at the end of one chunk and whose figure sits at the start of the next is retrievable from neither chunk without it.
- **Why page by page**: the page number *is* the citation. A whole-document `export_to_markdown()` flattens away Docling's provenance, so every chunk came back with `page: None` and every internal citation rendered "Page: N/A" while the citation plumbing and Sources panel sat fully built. Exporting one page at a time preserves the Markdown structure the splitter needs and gives each chunk a real page.
- **What page-by-page costs**: a chunk never straddles a page break, so every page ends in a short tail chunk, and the 200-character overlap does not carry across the boundary — a sentence split by a page break is the one case overlap cannot rescue. Taken deliberately: a chunk spanning two pages can only be labelled with one of them, and a citation pointing at the wrong page is worse than a slightly smaller chunk. Documents with no page provenance still fall back to a whole-document split with no page number.

These numbers are reasoned from model input limits, not tuned against a retrieval benchmark. There is no hit-rate / MRR / NDCG harness yet, so "1000 beats 800" is not a claim this document makes — only that 1000 is the largest size the two models in this pipeline can actually consume.

### Retrieval Relevance
- **Hybrid Search**: Dual indexing in `rag.py` — `HNSW` (via `vecs`) for semantic vector similarity, plus a GIN index over `to_tsvector('english', metadata->>'text')` for keyword retrieval. `vecs` only exposes vector indexes, so the lexical half is PostgreSQL full-text search ranked by `ts_rank_cd` rather than BM25; both halves run per sub-query and merge into one deduplicated candidate pool.
- **Sub-Query Expansion**: `services/query_rewriter.py` asks a lightweight LLM for three semantically distinct sub-queries and dispatches all of them, falling back to the original query on any failure. This widens recall across phrasings the document uses and the user did not.

### Retrieval Precision
- **Cross-Encoder Re-ranking**: `cross-encoder/ms-marco-MiniLM-L-6-v2` re-scores the merged pool against the *original* query — up to 10 candidates per sub-query per retrieval half, deduplicated by chunk ID — and the top 5 go to the requesting agent.
- **Abstention Gate**: if the pool's best score falls below `RAG_MIN_RERANK_SCORE`, retrieval returns nothing and tells the agent to use `web_search` instead. The pool is built recall-first and so is almost never empty; without this gate, a question the documents never address still produced confidently-formatted, citable-looking excerpts. The gate is pool-level rather than per-chunk because calibration ([`evals/rerank_calibration.py`](../backend/evals/rerank_calibration.py)) shows this model's absolute scores separate *"the corpus isn't about this"* but **not** *"answers the question"* from *"same topic, doesn't"*. The `−11.0` default is measured, not assumed — an intuitive `0.0` (the model's MS MARCO boundary) would have hidden 9 of 12 genuinely relevant passages.

### Retrieval Scoping
- **Semantic Metadata Filtering**: Implemented a `vertical` tagging system. 
  - **Ingestion**: Supports optional `vertical` categorization of document chunks.
  - **Retrieval**: `search_documents` now accepts an optional `vertical_filter`, applying a `query_filter` at the database level to limit retrieval to relevant document subsets.

---
*For technical implementation details, refer to the source code in `backend/` and the specific module files (`rag.py`, `pdf_service.py`, `query_rewriter.py`).*
