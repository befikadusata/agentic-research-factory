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

### Embedding Throughput
- **Batched Gemini embedding**: `_gemini_embed` sends up to 100 texts per `batchEmbedContents` call instead of one `embedContent` call per text. Ingest previously cost one HTTP round trip per chunk — a 200-chunk PDF meant 200 sequential requests, each paying connection setup and carrying its own retry envelope. Measured on 20 corpus chunks against the live API: **12.33s → 1.79s, a 6.9× speed-up** (617 ms/chunk to 89 ms/chunk). 100 is the API's hard ceiling, not a tuning choice — it rejects larger batches outright.
- **Embedding cache** ([`utils/embedding_cache.py`](../backend/utils/embedding_cache.py)): Redis, content-addressed, keyed on **provider + model + dimension + text**. Embedding the same text with the same model is deterministic, so every repeat is a paid round trip for a known answer, and repeats are common: a ReAct agent's tool loop fires `search_documents` several times per node, a review `FAIL` re-runs the whole research segment, sub-query expansion at temperature 0.4 emits near-duplicates and often the original query verbatim, and re-ingesting an edited document re-embeds every chunk that did not change. Measured on 3 repeated queries: **1628 ms → 0.8 ms**.

  The key covers the model and dimension, not just the text, because vectors from two models are not comparable and `rag.py` refuses to mix them at runtime for exactly that reason. A cache keyed on text alone would reintroduce the bug the moment `GEMINI_API_KEY` was set or cleared. Keyed this way, switching providers simply misses everything, which is self-healing. Values are packed little-endian float32 — explicit byte order because a byte-swapped vector has the right length and plausible magnitudes, so it would degrade retrieval silently rather than fail. float32 loses nothing that survives storage: pgvector's element type is single precision, and the retrieval eval returns identical metrics with the cache in the path.

  It never raises. A broken Redis and a cache miss are the same thing to the caller — compute it — because a cache that can fail the operation it accelerates is worse than no cache. Disabled under pytest, so a shared store cannot make "did this call the embedder?" assertions depend on what an earlier test warmed.

### Retrieval Relevance
- **Hybrid Search**: Dual indexing in `rag.py` — `HNSW` (via `vecs`) for semantic vector similarity, plus a GIN index over `to_tsvector('english', metadata->>'text')` for keyword retrieval. `vecs` only exposes vector indexes, so the lexical half is PostgreSQL full-text search ranked by `ts_rank_cd` rather than BM25; both halves run per sub-query and merge into one deduplicated candidate pool.

  The lexical half matches **any** query term, not all of them. `plainto_tsquery` ANDs every lexeme, which suits a bag of keywords and fails on the question-shaped strings agents actually send: `"What does ACM-429 mean?"` becomes `'acm' & '-429' & 'mean'`, so the one chunk documenting that error code does not match unless it also says "mean". The retrieval eval caught this as a candidate pool sitting at exactly the vector half's limit for **every** query — hybrid search had silently stopped being hybrid, with no error anywhere. `websearch_to_tsquery` over `or`-joined terms restores disjunction while keeping hyphenated identifiers as phrases, and `ts_rank_cd` still ranks chunks matching more of the query higher.
- **Sub-Query Expansion**: `services/query_rewriter.py` asks a lightweight LLM for three semantically distinct sub-queries and dispatches all of them, falling back to the original query on any failure. This widens recall across phrasings the document uses and the user did not.

### Retrieval Precision
- **Cross-Encoder Re-ranking**: `cross-encoder/ms-marco-MiniLM-L-6-v2` re-scores the merged pool against the *original* query — up to 10 candidates per sub-query per retrieval half, deduplicated by chunk ID — and the top 5 go to the requesting agent. `tools.rag.retrieve` returns the whole ranked pool; the gate and the top-5 cut are policy applied above it, so an eval can measure the ranking rather than the truncation.
- **Abstention Gate**: if the pool's best score falls below `RAG_MIN_RERANK_SCORE`, retrieval returns nothing and tells the agent to use `web_search` instead. The pool is built recall-first and so is almost never empty; without this gate, a question the documents never address still produced confidently-formatted, citable-looking excerpts. The gate is pool-level rather than per-chunk because both instruments below agree that this model's absolute scores separate *"the corpus isn't about this"* but **not** *"answers the question"* from *"same topic, doesn't"*. The `−9.0` default is measured against the pipeline — see the next section.

### Context Assembly
- **Neighbour expansion** (`tools.rag.expand_context`, `RAG_NEIGHBOUR_RADIUS`): each surviving chunk is widened by the chunk either side of it before the agent sees it. Retrieval ranks 1000-character windows because that is the largest span the embedder and the re-ranker read in full — but 1000 characters is a model input limit, not a unit of meaning. The window that scores highest is regularly the one that *names* the thing, while the sentence qualifying it sits in the next window and never arrives. Retrieving small and reading large is the standard answer, and here it costs one indexed lookup per search.

  Chunks carry an `ordinal` — their position in their own document — assigned in `ingest_documents` rather than by each parser, so docling, LlamaParse, and the eval corpus all get it and a future producer cannot forget. Lookup is by `(source, ordinal)` against a B-tree over those two expressions; without the index this would be a sequential scan of the collection on every search.

  **Expansion stops at a page boundary.** The page number is the citation — it is the entire reason ingest splits page by page — and a passage spanning two pages can only be labelled with one of them. Chunks never straddle a break, so a run is always wholly on one page and carries one exact citation.

  Adjacent chunks are **stitched, not concatenated**: they repeat `chunk_overlap` characters by construction, so joining them naively makes the document appear to say the same thing twice. The overlap is a literal shared substring, so it is measured rather than assumed — the splitter cuts at separators, so the real figure is rarely the configured 200. `tests/test_rag_context.py` verifies this by splitting a real passage with the configured `RecursiveCharacterTextSplitter` and asserting the stitched result is character-identical to the original.

  Everything degrades rather than fails. Chunks ingested before ordinals existed have none, and nothing backfills them — those documents return unexpanded, exactly as before, until they are re-uploaded. A radius of 0 disables expansion, and a neighbour lookup that raises is logged and skipped: expansion is an enhancement, and losing it must not lose the answer. The results themselves are never dropped; only the neighbours are budgeted, against a `_MAX_CONTEXT_CHUNKS` ceiling of 12, so a bound that binds degrades to the old behaviour.

### Evaluation
Two instruments, measuring different things, and the difference between them turned out to matter more than either number.

- **[`evals/rerank_calibration.py`](../backend/evals/rerank_calibration.py)** scores 34 labelled `(query, passage)` pairs with the real cross-encoder. It establishes the score distribution on business-document prose — and that relevant and same-topic-but-wrong overlap almost entirely, which is what rules out a per-chunk relevance filter.
- **[`evals/retrieval_baselines.py`](../backend/evals/retrieval_baselines.py)** supplies the ablations the pipeline is measured against — naive dense top-k and dense + re-ranking — so each stage has to justify its cost rather than being paid for on the strength of the paper it came from. Run through `--compare`.
- **[`evals/retrieval_eval.py`](../backend/evals/retrieval_eval.py)** ingests a 54-chunk corpus through the real ingest path and runs 62 golden queries plus 10 unanswerable ones through the real `retrieve()`. It reports hit@{1,3,5,10}, MRR, NDCG@k, and **pool recall** — whether the chunk was in the candidate pool at any depth, which is what says whether a miss is a recall failure (the fan-out lost it, and no re-ranker change recovers it) or a ranking failure. It also reports **coverage**, the fraction of a query's answering chunks that reach the agent, once over the ranking and once over what neighbour expansion actually delivers. Results are sliced by query kind: `lookup`, `paraphrase`, `exact-term`, `multi-chunk`, `near-miss`.

```
hit@1 0.790   hit@3 0.871   hit@5 0.903   hit@10 0.968
MRR 0.846     NDCG@5 0.813  NDCG@10 0.844  pool recall 1.000
coverage 0.895 ranked -> 0.903 delivered   (multi-chunk 0.700 -> 0.800)
mean 7.8 chunks in 4.6 blocks per search
```

hit@k asks whether retrieval found *an* answer; coverage asks whether it found the whole one, which is the question a multi-chunk query actually poses and the one neighbour expansion is meant to move.

Sub-query expansion is pinned off by default so a re-run measures retrieval rather than that day's LLM rewrite; `--expand` measures the production path, and the report always states which was used.

**Compared against what.** `--compare` runs [`evals/retrieval_baselines.py`](../backend/evals/retrieval_baselines.py): the same corpus and queries against naive dense top-k, then dense + re-ranking, then production. Each variant adds one stage, so the differences say what each stage is worth. On this corpus the answer is uncomfortable:

```
variant           hit@1  hit@5    MRR  ndcg@5  recall  cover   pool   rejects unanswerable
dense             0.871  0.984  0.930   0.923   1.000  0.984   10.0   0/10 (no gate)
dense+rerank      0.790  0.968  0.858   0.852   1.000  0.960   10.0            7/10
hybrid+rerank     0.790  0.903  0.846   0.813   1.000  0.895   13.4            7/10
```

**Naive dense retrieval outranks the full pipeline here, and both stages above it cost accuracy.** The cause is the same one the lexical-half note gives: 54 chunks is small enough that the dense half alone reaches pool recall 1.000, so there is no recall left to recover — the lexical fan-out can only contribute distractors, and the cross-encoder can only reorder a list that was already right. `ms-marco-MiniLM-L-6-v2` is a small model trained on web QA, and on business prose it is simply a weaker judge than the embedder.

What the pipeline does win, categorically, is the last column. Dense top-k has no abstention gate available to it — cosine similarity is not on the cross-encoder's scale — so it answers all ten unanswerable queries with confidently-formatted excerpts, which is the fabricated-citation failure the gate exists to stop. On this corpus that is the whole of what the cross-encoder buys, and it is enough to keep it.

The rest of the pipeline is running on an untested bet: that dense recall stops being perfect as a workspace grows past a few dozen chunks, at which point the fan-out starts recovering answers instead of adding noise. That bet is plausible and standard, and it is *not* evidence — this harness cannot settle it, and it should not be described as if it had. `tests/test_retrieval_eval.py` asserts on the gap rather than on a winner, so it stays quiet if the pipeline improves and fires if it drifts further behind the baseline.

**The threshold was set from the wrong instrument.** The calibration put off-topic pairs in a tight band near −11.2, so −11.0 looked like the natural cut. Against the real pipeline it rejected **1 of 10** unanswerable queries. The gate never sees a passage in isolation — it sees the best chunk retrieval could find anywhere in the corpus, and best-of-pool scores run far above isolated-pair scores. Moving to −9.0 takes correct rejections from 1/10 to 7/10 at no measured cost in false abstentions (1/62 either way, and that one is a colloquial paraphrase −11.0 already missed). It is deliberately not pushed to −8.5, where the numbers look better still, because the lowest answerable query that passes scores −8.351 and a threshold 0.15 away from a real answer is tuned to this corpus rather than robust to the next one.

**Known limits.** 54 chunks is small enough that the vector half alone achieves pool recall 1.000, so this corpus cannot demonstrate the lexical half's contribution to recall — it can only show its cost, and it does: fixing the any-term bug widened the mean pool from 10.0 to 13.3 and moved hit@5 from 0.968 down to 0.903, because the extra candidates are distractors the re-ranker sometimes prefers. (The ablation above confirms this from the other direction: `dense+rerank` scores 0.968, which is exactly what production measured while the lexical half was silently dead.) That trade should invert at production corpus sizes, where vector recall stops being perfect, but this harness cannot show it.

Neighbour expansion has the same shape of limit, for a different reason. Every chunk in this corpus is a self-contained paragraph, so nothing in it is a sentence severed from its qualifier — which is the case expansion exists for. What the harness can say is that expansion costs nothing measurable (coverage rose, no ranking metric moved) and delivers 7.8 chunks where the ranking alone delivered 5. The mechanism is verified separately, by round-tripping a real passage through the configured splitter and asserting the stitch reproduces it exactly.

The corpus is also synthetic — real customer documents cannot live in the repository, and a public benchmark would measure web prose, the exact mismatch that made the first threshold wrong. Nothing here measures answer quality; the harness stops at the retrieval boundary on purpose.

### Retrieval Scoping
- **Semantic Metadata Filtering**: Implemented a `vertical` tagging system. 
  - **Ingestion**: Supports optional `vertical` categorization of document chunks.
  - **Retrieval**: `search_documents` now accepts an optional `vertical_filter`, applying a `query_filter` at the database level to limit retrieval to relevant document subsets.

---
*For technical implementation details, refer to the source code in `backend/` and the specific module files (`rag.py`, `pdf_service.py`, `query_rewriter.py`).*
