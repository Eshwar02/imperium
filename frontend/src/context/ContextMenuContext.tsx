// Context-menu service — a single portal menu opened at the cursor from anywhere.
// Usage:
//   const menu = useContextMenu();
//   <div onContextMenu={(e) => menu.open(e, [{ label: "Close", onClick: ... }])} />
import {
  createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { t } from "../theme";

export interface MenuEntry {
  label?: string;
  onClick?: () => void;
  disabled?: boolean;
  danger?: boolean;
  separator?: boolean;
  hint?: string; // right-aligned keybinding hint
}

interface OpenState { x: number; y: number; items: MenuEntry[] }

interface ContextMenuCtx {
  open: (e: { clientX: number; clientY: number; preventDefault: () => void }, items: MenuEntry[]) => void;
  close: () => void;
}

const Ctx = createContext<ContextMenuCtx | null>(null);

export function ContextMenuProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<OpenState | null>(null);

  const open: ContextMenuCtx["open"] = useCallback((e, items) => {
    e.preventDefault();
    if (items.length === 0) return;
    setState({ x: e.clientX, y: e.clientY, items });
  }, []);
  const close = useCallback(() => setState(null), []);

  return (
    <Ctx.Provider value={{ open, close }}>
      {children}
      {state && <MenuSurface state={state} onClose={close} />}
    </Ctx.Provider>
  );
}

function MenuSurface({ state, onClose }: { state: OpenState; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: state.x, y: state.y });

  // Keep the menu on-screen.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    let { x, y } = state;
    if (x + r.width > window.innerWidth) x = Math.max(4, window.innerWidth - r.width - 4);
    if (y + r.height > window.innerHeight) y = Math.max(4, window.innerHeight - r.height - 4);
    setPos({ x, y });
  }, [state]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onDown = (e: MouseEvent) => {
      if (ref.current && ref.current.contains(e.target as Node)) return; // click inside menu
      onClose();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown, true);
    window.addEventListener("resize", onClose);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown, true);
      window.removeEventListener("resize", onClose);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={ref}
      role="menu"
      onMouseDown={(e) => e.stopPropagation()}
      style={{
        position: "fixed", left: pos.x, top: pos.y, zIndex: 10000, minWidth: 200,
        background: t.bgElev, border: `1px solid ${t.border}`, borderRadius: 6,
        boxShadow: t.shadow, padding: "4px 0", fontFamily: t.sans, fontSize: 13,
      }}
    >
      {state.items.map((it, i) =>
        it.separator ? (
          <div key={i} style={{ height: 1, background: t.border, margin: "4px 0" }} />
        ) : (
          <MenuRow key={i} entry={it} onClose={onClose} />
        ),
      )}
    </div>,
    document.body,
  );
}

function MenuRow({ entry, onClose }: { entry: MenuEntry; onClose: () => void }) {
  const [hover, setHover] = useState(false);
  const disabled = !!entry.disabled;
  return (
    <div
      role="menuitem"
      aria-disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={() => {
        if (disabled) return;
        onClose();
        entry.onClick?.();
      }}
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24,
        padding: "5px 12px", cursor: disabled ? "default" : "pointer",
        color: disabled ? t.textDim : entry.danger ? t.red : t.text,
        background: hover && !disabled ? t.bgHover : "transparent",
        opacity: disabled ? 0.6 : 1, whiteSpace: "nowrap",
      }}
    >
      <span>{entry.label}</span>
      {entry.hint && <span style={{ color: t.textDim, fontSize: 11 }}>{entry.hint}</span>}
    </div>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useContextMenu() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useContextMenu must be inside ContextMenuProvider");
  return c;
}
