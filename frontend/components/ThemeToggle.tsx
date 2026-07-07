"use client";

import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

const STORAGE_KEY = "ftm-theme";

export function ThemeToggle() {
  const [light, setLight] = useState(false);

  useEffect(() => {
    setLight(document.documentElement.classList.contains("light"));
  }, []);

  function toggle() {
    const next = !light;
    setLight(next);
    document.documentElement.classList.toggle("light", next);
    localStorage.setItem(STORAGE_KEY, next ? "light" : "dark");
  }

  return (
    <button
      onClick={toggle}
      aria-label={light ? "Switch to dark mode" : "Switch to light mode"}
      className="text-content-secondary hover:text-content px-4 py-2 rounded-md flex items-center gap-3 transition-colors w-full"
    >
      {light ? <Moon size={18} /> : <Sun size={18} />}
      {light ? "Dark mode" : "Light mode"}
    </button>
  );
}
