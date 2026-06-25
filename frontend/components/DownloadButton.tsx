interface Props {
  onClick: () => void;
  label: string;
  variant?: "primary" | "secondary";
  disabled?: boolean;
}

export function DownloadButton({ onClick, label, variant = "secondary", disabled }: Props) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-block text-sm font-medium px-4 py-2 rounded-lg transition-colors
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variant === "primary"
          ? "bg-violet-600 hover:bg-violet-700 text-white"
          : "border border-zinc-600 hover:bg-zinc-700 text-zinc-200"}`}
    >
      {label}
    </button>
  );
}
