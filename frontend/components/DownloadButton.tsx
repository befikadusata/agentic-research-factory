interface Props {
  href: string;
  label: string;
  variant?: "primary" | "secondary";
}

export function DownloadButton({ href, label, variant = "secondary" }: Props) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={`inline-block text-sm font-medium px-4 py-2 rounded-lg transition-colors
        ${variant === "primary"
          ? "bg-violet-600 hover:bg-violet-700 text-white"
          : "border border-zinc-600 hover:bg-zinc-700 text-zinc-200"}`}
    >
      {label}
    </a>
  );
}
