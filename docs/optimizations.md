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

### Retrieval Stability
- **Recursive Splitting**: Replaced character-based splitting with `RecursiveCharacterTextSplitter` (`chunk_size=1000`, `overlap=200`) in `pdf_service.py` to maintain contextual coherence in retrieved documents.

### Retrieval Relevance
- **Hybrid Search**: Implemented `vecs` with dual indexing (`BM25` for keyword retrieval + `HNSW` for semantic vector similarity) in `rag.py`.
- **Query Rewriting**: Integrated a dedicated service (`services/query_rewriter.py`) utilizing a lightweight LLM to expand user queries, effectively bridging semantic gaps between user intent and document content.

### Retrieval Precision
- **Cross-Encoder Re-ranking**: Added a `cross-encoder/ms-marco-MiniLM-L-6-v2` re-ranker. The pipeline now retrieves 20 candidate documents via Hybrid Search and re-ranks them based on query-relevance scores, returning the top 5 most pertinent results.

### Retrieval Scoping
- **Semantic Metadata Filtering**: Implemented a `vertical` tagging system. 
  - **Ingestion**: Supports optional `vertical` categorization of document chunks.
  - **Retrieval**: `search_documents` now accepts an optional `vertical_filter`, applying a `query_filter` at the database level to limit retrieval to relevant document subsets.

---
*For technical implementation details, refer to the source code in `backend/` and the specific module files (`rag.py`, `pdf_service.py`, `query_rewriter.py`).*
