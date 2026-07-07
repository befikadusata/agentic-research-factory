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
      className={`inline-block text-sm font-medium px-4 py-2 rounded-md transition-colors duration-base
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variant === "primary"
          ? "bg-primary hover:bg-primary-hover text-primary-on"
          : "border border-border-strong hover:bg-surface-3 text-content-secondary"}`}
    >
      {label}
    </button>
  );
}
