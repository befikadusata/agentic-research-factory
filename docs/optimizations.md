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

These numbers are reasoned from model input limits, not tuned against a retrieval benchmark. The eval harness below measures whether retrieval *finds* the right chunk, not whether a different chunk size would find it more often, so "1000 beats 800" is still not a claim this document makes — only that 1000 is the largest size the two models in this pipeline can actually consume.

### Retrieval Relevance
- **Hybrid Search**: Dual indexing in `rag.py` — `HNSW` (via `vecs`) for semantic vector similarity, plus a GIN index over `to_tsvector('english', metadata->>'text')` for keyword retrieval. `vecs` only exposes vector indexes, so the lexical half is PostgreSQL full-text search ranked by `ts_rank_cd` rather than BM25; both halves run per sub-query and merge into one deduplicated candidate pool.

  The lexical half matches **any** query term, not all of them. `plainto_tsquery` ANDs every lexeme, which suits a bag of keywords and fails on the question-shaped strings agents actually send: `"What does ACM-429 mean?"` becomes `'acm' & '-429' & 'mean'`, so the one chunk documenting that error code does not match unless it also says "mean". The retrieval eval caught this as a candidate pool sitting at exactly the vector half's limit for **every** query — hybrid search had silently stopped being hybrid, with no error anywhere. `websearch_to_tsquery` over `or`-joined terms restores disjunction while keeping hyphenated identifiers as phrases, and `ts_rank_cd` still ranks chunks matching more of the query higher.
- **Sub-Query Expansion**: `services/query_rewriter.py` asks a lightweight LLM for three semantically distinct sub-queries and dispatches all of them, falling back to the original query on any failure. This widens recall across phrasings the document uses and the user did not.

### Retrieval Precision
- **Cross-Encoder Re-ranking**: `cross-encoder/ms-marco-MiniLM-L-6-v2` re-scores the merged pool against the *original* query — up to 10 candidates per sub-query per retrieval half, deduplicated by chunk ID — and the top 5 go to the requesting agent. `tools.rag.retrieve` returns the whole ranked pool; the gate and the top-5 cut are policy applied above it, so an eval can measure the ranking rather than the truncation.
- **Abstention Gate**: if the pool's best score falls below `RAG_MIN_RERANK_SCORE`, retrieval returns nothing and tells the agent to use `web_search` instead. The pool is built recall-first and so is almost never empty; without this gate, a question the documents never address still produced confidently-formatted, citable-looking excerpts. The gate is pool-level rather than per-chunk because both instruments below agree that this model's absolute scores separate *"the corpus isn't about this"* but **not** *"answers the question"* from *"same topic, doesn't"*. The `−9.0` default is measured against the pipeline — see the next section.

### Evaluation
Two instruments, measuring different things, and the difference between them turned out to matter more than either number.

- **[`evals/rerank_calibration.py`](../backend/evals/rerank_calibration.py)** scores 34 labelled `(query, passage)` pairs with the real cross-encoder. It establishes the score distribution on business-document prose — and that relevant and same-topic-but-wrong overlap almost entirely, which is what rules out a per-chunk relevance filter.
- **[`evals/retrieval_eval.py`](../backend/evals/retrieval_eval.py)** ingests a 54-chunk corpus through the real ingest path and runs 62 golden queries plus 10 unanswerable ones through the real `retrieve()`. It reports hit@{1,3,5,10}, MRR, NDCG@k, and **pool recall** — whether the chunk was in the candidate pool at any depth, which is what says whether a miss is a recall failure (the fan-out lost it, and no re-ranker change recovers it) or a ranking failure. Results are sliced by query kind: `lookup`, `paraphrase`, `exact-term`, `multi-chunk`, `near-miss`.

```
hit@1 0.790   hit@3 0.871   hit@5 0.903   hit@10 0.968
MRR 0.846     NDCG@5 0.813  NDCG@10 0.844  pool recall 1.000
```

Sub-query expansion is pinned off by default so a re-run measures retrieval rather than that day's LLM rewrite; `--expand` measures the production path, and the report always states which was used.

**The threshold was set from the wrong instrument.** The calibration put off-topic pairs in a tight band near −11.2, so −11.0 looked like the natural cut. Against the real pipeline it rejected **1 of 10** unanswerable queries. The gate never sees a passage in isolation — it sees the best chunk retrieval could find anywhere in the corpus, and best-of-pool scores run far above isolated-pair scores. Moving to −9.0 takes correct rejections from 1/10 to 7/10 at no measured cost in false abstentions (1/62 either way, and that one is a colloquial paraphrase −11.0 already missed). It is deliberately not pushed to −8.5, where the numbers look better still, because the lowest answerable query that passes scores −8.351 and a threshold 0.15 away from a real answer is tuned to this corpus rather than robust to the next one.

**Known limits.** 54 chunks is small enough that the vector half alone achieves pool recall 1.000, so this corpus cannot demonstrate the lexical half's contribution to recall — it can only show its cost, and it does: fixing the any-term bug widened the mean pool from 10.0 to 13.3 and moved hit@5 from 0.968 down to 0.903, because the extra candidates are distractors the re-ranker sometimes prefers. That trade inverts at production corpus sizes, where vector recall stops being perfect, but this harness cannot show it. The corpus is also synthetic — real customer documents cannot live in the repository, and a public benchmark would measure web prose, the exact mismatch that made the first threshold wrong. Nothing here measures answer quality; the harness stops at the retrieval boundary on purpose.

### Retrieval Scoping
- **Semantic Metadata Filtering**: Implemented a `vertical` tagging system. 
  - **Ingestion**: Supports optional `vertical` categorization of document chunks.
  - **Retrieval**: `search_documents` now accepts an optional `vertical_filter`, applying a `query_filter` at the database level to limit retrieval to relevant document subsets.

---
*For technical implementation details, refer to the source code in `backend/` and the specific module files (`rag.py`, `pdf_service.py`, `query_rewriter.py`).*
