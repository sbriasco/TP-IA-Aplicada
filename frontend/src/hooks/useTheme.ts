import { useEffect, useState } from "react";

export type Theme = "light" | "dark";
const KEY = "flowsight-theme";

export function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch { /* Storage may be unavailable in a private browser session. */ }
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => applyTheme(theme), [theme]);
  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try { localStorage.setItem(KEY, next); } catch { /* Keep the toggle usable without storage. */ }
  }
  return { theme, toggleTheme };
}
