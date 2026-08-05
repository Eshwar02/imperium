// Dark IDE theme tokens — one source of truth so every panel matches.
export const t = {
  bg: "#0d1117",
  bgPanel: "#161b22",
  bgElev: "#1c2128",
  bgHover: "#21262d",
  border: "#30363d",
  text: "#e6edf3",
  textDim: "#7d8590",
  accent: "#2f81f7",
  green: "#3fb950",
  red: "#f85149",
  yellow: "#d29922",
  purple: "#a371f7",
  mono: "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace",
  sans: "system-ui, -apple-system, 'Segoe UI', sans-serif",
};

export const catColor: Record<string, string> = {
  security: t.red,
  performance: t.yellow,
  modernization: t.purple,
  integration: t.accent,
  documentation: t.textDim,
};
