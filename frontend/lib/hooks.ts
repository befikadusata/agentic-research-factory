import { useState, useEffect } from "react";
import type { Run, SSEEvent } from "@/lib/types";

export function useRunStream(id: string) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const eventSource = new EventSource(`/api/runs/${id}/stream`);

    eventSource.onmessage = (event) => {
      const data: SSEEvent = JSON.parse(event.data);
      if (data.type === "status") {
        setRun((prev) => prev ? { ...prev, status: data.data.status } : null);
      }
    };

    eventSource.onerror = () => {
      setError("Stream connection lost");
      eventSource.close();
    };

    return () => eventSource.close();
  }, [id]);

  return { run, error };
}
