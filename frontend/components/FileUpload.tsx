"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadFile } from "@/lib/api";

interface Props {
  workspaceId: string | null;
  onUploaded: (docId: string, filename: string) => void;
  onRemoved?: () => void;
}

export function FileUpload({ workspaceId, onUploaded, onRemoved }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

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
      setUploadedFileName(file.name);
      onUploaded(doc_id, file.name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [onUploaded, workspaceId]);

  function handleRemove() {
    setUploadedFileName(null);
    setError(null);
    onRemoved?.();
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    disabled: uploading || uploadedFileName !== null,
  });

  return (
    <div>
      <p className="text-xs text-content-muted mb-2">PDF only · max 1 file</p>
      {uploadedFileName ? (
        <div className="border-2 border-feedback-success/40 bg-feedback-success/10 rounded-lg p-4 flex items-center justify-between">
          <span className="text-content text-sm font-medium">✓ {uploadedFileName}</span>
          <button
            type="button"
            onClick={handleRemove}
            className="text-content-muted hover:text-content text-xs ml-4 underline transition-colors"
          >
            Remove
          </button>
        </div>
      ) : (
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
