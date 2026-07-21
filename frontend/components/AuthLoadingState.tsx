import { LayoutGrid, LoaderCircle } from "lucide-react";

export function AuthLoadingState({
  title = "Checking your session",
  description = "Securely loading your workspace.",
  fullScreen = false,
}: {
  title?: string;
  description?: string;
  fullScreen?: boolean;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center justify-center px-4 py-10 ${fullScreen ? "min-h-dvh" : "min-h-[60vh]"}`}
    >
      <div className="w-full max-w-sm rounded-xl border border-border-subtle bg-surface-1 p-6 text-center shadow-hairline sm:p-8">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
          <LayoutGrid size={24} aria-hidden />
        </div>
        <LoaderCircle
          size={22}
          className="mx-auto mt-6 animate-spin text-primary motion-reduce:animate-none"
          aria-hidden
        />
        <p className="mt-4 text-base font-semibold text-content">{title}</p>
        <p className="mt-1 text-sm leading-6 text-content-secondary">{description}</p>
      </div>
    </div>
  );
}
