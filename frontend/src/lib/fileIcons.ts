// Map file names/extensions to a glyph (for the Explorer) and a Monaco language id.
const EXT_LANG: Record<string, string> = {
  ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript",
  mjs: "javascript", cjs: "javascript", json: "json", py: "python",
  rb: "ruby", go: "go", rs: "rust", java: "java", kt: "kotlin",
  c: "c", h: "c", cpp: "cpp", cc: "cpp", hpp: "cpp", cs: "csharp",
  php: "php", swift: "swift", scala: "scala", sh: "shell", bash: "shell",
  zsh: "shell", yml: "yaml", yaml: "yaml", toml: "ini", ini: "ini",
  md: "markdown", markdown: "markdown", html: "html", htm: "html",
  css: "css", scss: "scss", less: "less", sql: "sql", xml: "xml",
  dockerfile: "dockerfile", cob: "cobol", cbl: "cobol", jcl: "jcl",
  graphql: "graphql", vue: "html", svelte: "html",
};

const EXT_ICON: Record<string, string> = {
  ts: "🇹", tsx: "⚛", js: "🇯", jsx: "⚛", json: "◆", py: "🐍",
  md: "📝", markdown: "📝", html: "🌐", css: "🎨", scss: "🎨",
  yml: "⚙", yaml: "⚙", toml: "⚙", ini: "⚙", env: "🔑", lock: "🔒",
  sh: "❯", bash: "❯", sql: "🗄", go: "🐹", rs: "🦀", java: "☕",
  png: "🖼", jpg: "🖼", jpeg: "🖼", gif: "🖼", svg: "🖼", ico: "🖼",
  cob: "📘", cbl: "📘", jcl: "📗",
};

const NAME_ICON: Record<string, string> = {
  "package.json": "📦", "package-lock.json": "🔒", "tsconfig.json": "🇹",
  "dockerfile": "🐳", "docker-compose.yml": "🐳", ".gitignore": "🚫",
  "readme.md": "📖", "license": "⚖", ".env": "🔑", ".env.example": "🔑",
  "makefile": "🛠", "vite.config.ts": "⚡", "pyproject.toml": "🐍",
};

function ext(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

export function fileIcon(name: string): string {
  const lower = name.toLowerCase();
  if (NAME_ICON[lower]) return NAME_ICON[lower];
  return EXT_ICON[ext(name)] ?? "📄";
}

export function monacoLanguage(name: string): string {
  const lower = name.toLowerCase();
  if (lower === "dockerfile") return "dockerfile";
  if (lower.startsWith(".env")) return "ini";
  return EXT_LANG[ext(name)] ?? "plaintext";
}
