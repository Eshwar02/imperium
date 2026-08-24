// Theme service — owns the active palette (dark/light), persists it, and applies
// it to <html> via CSS variables. Consumers just read/toggle; components keep
// using the `t.*` tokens from theme.ts unchanged.
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { applyTheme, type ThemeName } from "../theme";

interface ThemeCtx {
  theme: ThemeName;
  setTheme: (t: ThemeName) => void;
  toggleTheme: () => void;
}

const Ctx = createContext<ThemeCtx | null>(null);
const KEY = "imperium.theme";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeRaw] = useState<ThemeName>(
    () => (localStorage.getItem(KEY) as ThemeName) || "dark",
  );

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem(KEY, theme);
  }, [theme]);

  const setTheme = (t: ThemeName) => setThemeRaw(t);
  const toggleTheme = () => setThemeRaw((c) => (c === "dark" ? "light" : "dark"));

  return <Ctx.Provider value={{ theme, setTheme, toggleTheme }}>{children}</Ctx.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useTheme must be inside ThemeProvider");
  return c;
}
