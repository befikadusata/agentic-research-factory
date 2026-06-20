"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadFile } from "@/lib/api";

interface Props {
  onUploaded: (docId: string, filename: string) => void;
}

export function FileUpload({ onUploaded }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (accepted: File[]) => {
    const file = accepted[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const { doc_id } = await uploadFile(file);
      onUploaded(doc_id, file.name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [onUploaded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    disabled: uploading,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-violet-500 bg-violet-950/20" : "border-zinc-700 hover:border-zinc-500"}`}
      >
        <input {...getInputProps()} />
        <p className="text-zinc-400 text-sm">
          {uploading ? "Uploading…" : isDragActive ? "Drop PDF here" : "Drag & drop a PDF, or click to select"}
        </p>
      </div>
      {error && <p className="text-red-400 text-sm mt-1">{error}</p>}
    </div>
  );
}
