import { Moon, Sun } from "lucide-react";
import { useTheme } from "../hooks/useTheme";
import styles from "./ThemeToggle.module.css";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const label = theme === "dark" ? "Activar modo claro" : "Activar modo oscuro";
  return <button className={styles.toggle} type="button" onClick={toggleTheme} aria-label={label} title={label}>
    {theme === "dark" ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
  </button>;
}
