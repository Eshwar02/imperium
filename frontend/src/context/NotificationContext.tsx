// Notification service — VS Code-style toasts stacked bottom-right, with severity,
// optional action buttons, and auto-dismiss. Also exposes the live list so the
// status bar can show a bell/count.
import {
  createContext, useCallback, useContext, useRef, useState, type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { t } from "../theme";

export type Severity = "info" | "success" | "warning" | "error";

export interface NotifyOptions {
  timeout?: number | null; // ms; null = sticky
  actions?: { label: string; onClick: () => void }[];
}

export interface Notification {
  id: number;
  severity: Severity;
  message: string;
  actions?: { label: string; onClick: () => void }[];
}

interface NotificationCtx {
  notifications: Notification[];
  notify: (severity: Severity, message: string, opts?: NotifyOptions) => number;
  info: (m: string, o?: NotifyOptions) => number;
  success: (m: string, o?: NotifyOptions) => number;
  warning: (m: string, o?: NotifyOptions) => number;
  error: (m: string, o?: NotifyOptions) => number;
  dismiss: (id: number) => void;
  clearAll: () => void;
}

const Ctx = createContext<NotificationCtx | null>(null);

const ICON: Record<Severity, { glyph: string; color: string }> = {
  info: { glyph: "ⓘ", color: t.accent },
  success: { glyph: "✓", color: t.green },
  warning: { glyph: "⚠", color: t.yellow },
  error: { glyph: "⛔", color: t.red },
};

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setNotifications((list) => list.filter((n) => n.id !== id));
  }, []);

  const notify = useCallback<NotificationCtx["notify"]>((severity, message, opts) => {
    const id = nextId.current++;
    setNotifications((list) => [...list, { id, severity, message, actions: opts?.actions }]);
    const timeout = opts?.timeout === undefined ? 5000 : opts.timeout;
    if (timeout !== null) setTimeout(() => dismiss(id), timeout);
    return id;
  }, [dismiss]);

  const value: NotificationCtx = {
    notifications,
    notify,
    info: (m, o) => notify("info", m, o),
    success: (m, o) => notify("success", m, o),
    warning: (m, o) => notify("warning", m, o),
    error: (m, o) => notify("error", m, o),
    dismiss,
    clearAll: () => setNotifications([]),
  };

  return (
    <Ctx.Provider value={value}>
      {children}
      <Toaster notifications={notifications} onDismiss={dismiss} />
    </Ctx.Provider>
  );
}

function Toaster({ notifications, onDismiss }: {
  notifications: Notification[]; onDismiss: (id: number) => void;
}) {
  if (notifications.length === 0) return null;
  return createPortal(
    <div style={{
      position: "fixed", right: 16, bottom: 40, zIndex: 9000,
      display: "flex", flexDirection: "column", gap: 8, maxWidth: 380,
    }}>
      {notifications.map((n) => {
        const { glyph, color } = ICON[n.severity];
        return (
          <div key={n.id} role="alert" style={{
            background: t.bgElev, border: `1px solid ${t.border}`, borderLeft: `3px solid ${color}`,
            borderRadius: 6, boxShadow: t.shadow, padding: "10px 12px", fontFamily: t.sans,
            fontSize: 13, color: t.text, display: "flex", flexDirection: "column", gap: 8,
          }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
              <span style={{ color, flexShrink: 0 }}>{glyph}</span>
              <span style={{ flex: 1 }}>{n.message}</span>
              <button
                aria-label="Dismiss notification"
                onClick={() => onDismiss(n.id)}
                style={{ background: "none", border: "none", color: t.textDim, cursor: "pointer", fontSize: 14, lineHeight: 1 }}
              >✕</button>
            </div>
            {n.actions && n.actions.length > 0 && (
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                {n.actions.map((a, i) => (
                  <button key={i} onClick={() => { onDismiss(n.id); a.onClick(); }} style={{
                    fontSize: 12, padding: "3px 10px", borderRadius: 4, cursor: "pointer",
                    border: `1px solid ${t.border}`, background: t.accent, color: "#fff",
                  }}>{a.label}</button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>,
    document.body,
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotifications() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useNotifications must be inside NotificationProvider");
  return c;
}
