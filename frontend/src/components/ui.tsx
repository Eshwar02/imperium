// Shared presentational primitives for panels (keeps every panel consistent).
import type { CSSProperties, ReactNode } from "react";
import { t } from "../theme";

export function PanelShell({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, background: t.bgPanel }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "6px 12px", borderBottom: `1px solid ${t.border}`, flexShrink: 0 }}>
        <span style={{ fontSize: 11, letterSpacing: 0.6, textTransform: "uppercase", color: t.textDim, fontWeight: 700 }}>{title}</span>
        {right}
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "auto", padding: 10 }}>{children}</div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div style={{ color: t.textDim, fontSize: 13, padding: 12, fontStyle: "italic" }}>{children}</div>;
}

export function Badge({ children, color = t.textDim }: { children: ReactNode; color?: string }) {
  return (
    <span style={{ fontSize: 11, color, border: `1px solid ${color}55`, borderRadius: 4,
      padding: "1px 6px", background: `${color}18`, whiteSpace: "nowrap" }}>{children}</span>
  );
}

export function Btn({ children, onClick, kind = "default", disabled, style }: {
  children: ReactNode; onClick?: () => void; kind?: "default" | "primary" | "green" | "red"; disabled?: boolean; style?: CSSProperties;
}) {
  const bg = kind === "primary" ? t.accent : kind === "green" ? t.green : kind === "red" ? t.red : t.bgElev;
  const fg = kind === "default" ? t.text : "#fff";
  return (
    <button onClick={onClick} disabled={disabled}
      style={{ fontSize: 12, fontFamily: t.sans, padding: "4px 10px", borderRadius: 5,
        border: `1px solid ${kind === "default" ? t.border : "transparent"}`, background: bg, color: fg,
        cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1, ...style }}>
      {children}
    </button>
  );
}

export function Row({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div style={{ display: "flex", gap: 8, alignItems: "center", ...style }}>{children}</div>;
}
