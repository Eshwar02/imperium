// Dark/light IDE theme tokens — one source of truth so every panel matches.
// Tokens resolve to CSS custom properties, so switching palettes is a single
// `data-theme` swap on <html> with zero changes in consuming components.
export const t = {
  bg: "var(--bg)",
  bgPanel: "var(--bg-panel)",
  bgElev: "var(--bg-elev)",
  bgHover: "var(--bg-hover)",
  border: "var(--border)",
  text: "var(--text)",
  textDim: "var(--text-dim)",
  accent: "var(--accent)",
  green: "var(--green)",
  red: "var(--red)",
  yellow: "var(--yellow)",
  purple: "var(--purple)",
  shadow: "var(--shadow)",
  mono: "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace",
  sans: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};

export type ThemeName = "dark" | "light";

// Raw palettes behind the CSS variables above.
export const palettes: Record<ThemeName, Record<string, string>> = {
  dark: {
    "--bg": "#0d1117",
    "--bg-panel": "#161b22",
    "--bg-elev": "#1c2128",
    "--bg-hover": "#21262d",
    "--border": "#30363d",
    "--text": "#e6edf3",
    "--text-dim": "#7d8590",
    "--accent": "#2f81f7",
    "--green": "#3fb950",
    "--red": "#f85149",
    "--yellow": "#d29922",
    "--purple": "#a371f7",
    "--shadow": "0 8px 24px rgba(1,4,9,0.6)",
  },
  light: {
    "--bg": "#ffffff",
    "--bg-panel": "#f6f8fa",
    "--bg-elev": "#eaeef2",
    "--bg-hover": "#e3e7eb",
    "--border": "#d0d7de",
    "--text": "#1f2328",
    "--text-dim": "#59636e",
    "--accent": "#0969da",
    "--green": "#1a7f37",
    "--red": "#cf222e",
    "--yellow": "#9a6700",
    "--purple": "#8250df",
    "--shadow": "0 8px 24px rgba(140,149,159,0.3)",
  },
};

// Apply a palette by writing the CSS variables onto <html>.
export function applyTheme(name: ThemeName) {
  const root = document.documentElement;
  const p = palettes[name];
  for (const k in p) root.style.setProperty(k, p[k]);
  root.setAttribute("data-theme", name);
}

export const catColor: Record<string, string> = {
  security: t.red,
  performance: t.yellow,
  modernization: t.purple,
  integration: t.accent,
  documentation: t.textDim,
};
