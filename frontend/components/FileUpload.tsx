"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { AlertTriangle, LoaderCircle } from "lucide-react";
import { getDocument, uploadFile } from "@/lib/api";
import type { DocumentStatus } from "@/lib/types";

/** What the parent needs to know about the attached doc. `status` matters as
 *  much as the id: a "pending" doc has been stored but not yet chunked, so
 *  attaching it to a run would retrieve nothing. */
export interface AttachedDoc {
  docId: string;
  filename: string;
  status: DocumentStatus;
}

interface Props {
  workspaceId: string | null;
  onChange: (doc: AttachedDoc | null) => void;
}

const POLL_INTERVAL_MS = 1500;
// Ingestion is a PDF parse plus an embedding pass. Two minutes is generous for
// the single-file limit here; past that, something is wrong and saying so beats
// a spinner that never resolves.
const POLL_TIMEOUT_MS = 120_000;

export function FileUpload({ workspaceId, onChange }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [status, setStatus] = useState<DocumentStatus | null>(null);
  const [chunkCount, setChunkCount] = useState<number | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);

  // Held in a ref so the poll effect below doesn't restart every time the
  // parent re-renders with a fresh callback identity.
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0];
    if (!file) return;
    if (!workspaceId) {
      setError("Select a workspace before uploading.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const { doc_id } = await uploadFile(file, workspaceId);
      setDocId(doc_id);
      setFilename(file.name);
      // The upload response only means "stored". Chunking runs in a worker, so
      // the doc starts pending and the effect below waits for it to settle.
      setStatus("pending");
      setChunkCount(null);
      setIngestError(null);
      onChangeRef.current({ docId: doc_id, filename: file.name, status: "pending" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [workspaceId]);

  const isPending = status === "pending";

  useEffect(() => {
    if (!docId || !filename || !isPending) return;
    let cancelled = false;
    const startedAt = Date.now();

    function settle(next: DocumentStatus, chunks: number | null, message: string | null) {
      cancelled = true;
      setStatus(next);
      setChunkCount(chunks);
      setIngestError(message);
      onChangeRef.current({ docId: docId!, filename: filename!, status: next });
    }

    async function check() {
      if (cancelled) return;
      try {
        const state = await getDocument(docId!);
        if (cancelled) return;
        if (state.status === "pending") {
          if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
            settle("failed", null, "Indexing is still not finished. Remove the file and try again, or start the run without it.");
          }
          return;
        }
        settle(
          state.status,
          state.chunk_count ?? null,
          state.status === "failed"
            ? state.error_message || "This file could not be indexed."
            : null,
        );
      } catch {
        // A failed poll is usually a blip — keep trying until the timeout above
        // rather than declaring the document broken on one bad response.
      }
    }

    const timer = setInterval(check, POLL_INTERVAL_MS);
    void check(); // don't make the first result wait a full interval
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [docId, filename, isPending]);

  function handleRemove() {
    setDocId(null);
    setFilename(null);
    setStatus(null);
    setChunkCount(null);
    setIngestError(null);
    setError(null);
    onChangeRef.current(null);
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    disabled: uploading || docId !== null,
  });

  const removeButton = (
    <button
      type="button"
      onClick={handleRemove}
      className="text-content-muted hover:text-content text-xs ml-4 underline transition-colors"
    >
      Remove
    </button>
  );

  return (
    <div>
      <p className="text-xs text-content-muted mb-2">PDF only · max 1 file</p>

      {docId && status === "pending" && (
        <div role="status" className="border-2 border-agent-thinking/40 bg-agent-thinking/10 rounded-lg p-4 flex items-center justify-between">
          <span className="flex items-center gap-2 text-content text-sm font-medium">
            <LoaderCircle size={15} className="animate-spin" aria-hidden />
            Indexing {filename}…
          </span>
          {removeButton}
        </div>
      )}

      {docId && status === "ready" && (
        <div className="border-2 border-feedback-success/40 bg-feedback-success/10 rounded-lg p-4 flex items-center justify-between">
          <span className="text-content text-sm font-medium">
            ✓ {filename}
            {chunkCount != null && (
              <span className="text-content-secondary font-normal"> · {chunkCount} chunks indexed</span>
            )}
          </span>
          {removeButton}
        </div>
      )}

      {docId && status === "failed" && (
        <div role="alert" className="border-2 border-feedback-error/40 bg-feedback-error/10 rounded-lg p-4">
          <div className="flex items-start justify-between gap-2">
            <span className="flex items-start gap-2 text-content text-sm font-medium">
              <AlertTriangle size={15} className="mt-0.5 flex-none text-feedback-error" aria-hidden />
              {filename} could not be indexed
            </span>
            {removeButton}
          </div>
          {ingestError && (
            <p className="mt-2 text-xs text-content-secondary">{ingestError}</p>
          )}
        </div>
      )}

      {!docId && (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
            ${isDragActive ? "border-primary bg-primary/10" : "border-border-strong hover:border-content-muted"}
            ${uploading ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <input {...getInputProps()} />
          <p className="text-content-secondary text-sm">
            {uploading
              ? "Uploading…"
              : isDragActive
              ? "Drop PDF here"
              : "Drag & drop a PDF, or click to select"}
          </p>
        </div>
      )}

      {error && <p role="alert" className="text-content text-sm mt-1">{error}</p>}
    </div>
  );
}
