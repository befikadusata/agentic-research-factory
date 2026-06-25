"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadFile } from "@/lib/api";

interface Props {
  onUploaded: (docId: string, filename: string) => void;
  onRemoved?: () => void;
}

export function FileUpload({ onUploaded, onRemoved }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const { doc_id } = await uploadFile(file);
      setUploadedFileName(file.name);
      onUploaded(doc_id, file.name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [onUploaded]);

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
      <p className="text-xs text-zinc-500 mb-2">PDF only · max 1 file</p>
      {uploadedFileName ? (
        <div className="border-2 border-green-700/60 bg-green-950/20 rounded-lg p-4 flex items-center justify-between">
          <span className="text-green-400 text-sm font-medium">✓ {uploadedFileName}</span>
          <button
            type="button"
            onClick={handleRemove}
            className="text-zinc-500 hover:text-white text-xs ml-4 underline transition-colors"
          >
            Remove
          </button>
        </div>
      ) : (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
            ${isDragActive ? "border-violet-500 bg-violet-950/20" : "border-zinc-700 hover:border-zinc-500"}
            ${uploading ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          <input {...getInputProps()} />
          <p className="text-zinc-400 text-sm">
            {uploading
              ? "Uploading…"
              : isDragActive
              ? "Drop PDF here"
              : "Drag & drop a PDF, or click to select"}
          </p>
        </div>
      )}
      {error && <p className="text-red-400 text-sm mt-1">{error}</p>}
    </div>
  );
}
