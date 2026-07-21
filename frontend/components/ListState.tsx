import { RefreshCw } from "lucide-react";

export function CardListSkeleton({ label, count = 3 }: { label: string; count?: number }) {
  return (
    <div role="status" aria-label={label} className="space-y-4">
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          aria-hidden="true"
          className="animate-pulse rounded-lg border border-border-subtle bg-surface-2 p-4 sm:p-5"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="w-full space-y-3">
              <div className="h-4 w-2/3 rounded bg-surface-4" />
              <div className="h-3 w-1/3 rounded bg-surface-3" />
            </div>
            <div className="h-6 w-16 shrink-0 rounded bg-surface-3" />
          </div>
          <div className="mt-5 h-2 w-full rounded bg-surface-3" />
          <div className="mt-4 h-3 w-1/4 rounded bg-surface-3" />
        </div>
      ))}
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function LoadError({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry: () => void;
}) {
  return (
    <div role="alert" className="rounded-lg border border-feedback-error/40 bg-feedback-error/10 p-4 sm:p-5">
      <p className="font-semibold text-content">{title}</p>
      <p className="mt-1 text-sm text-content-secondary">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 flex min-h-11 items-center gap-2 rounded-md border border-border-subtle bg-surface-2 px-4 py-2 text-sm font-medium text-content transition-colors duration-base hover:border-primary hover:bg-surface-3"
      >
        <RefreshCw size={16} aria-hidden /> Retry
      </button>
    </div>
  );
}
