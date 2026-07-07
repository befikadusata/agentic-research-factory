"use client";

import { useEffect, useState } from "react";

/** Tracks the `light` class on <html>, set by ThemeToggle. */
export function useIsLightMode(): boolean {
  const [light, setLight] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    setLight(root.classList.contains("light"));

    const observer = new MutationObserver(() => {
      setLight(root.classList.contains("light"));
    });
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return light;
}
