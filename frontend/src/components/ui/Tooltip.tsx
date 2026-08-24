// Tooltip — hover/focus label that appears after a short delay, positioned around
// the wrapped element. Portaled so it never gets clipped by overflow containers.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { t } from "../../theme";

type Side = "top" | "bottom" | "left" | "right";

export default function Tooltip({
  label, children, side = "bottom", delay = 400,
}: {
  label: ReactNode; children: ReactNode; side?: Side; delay?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const [coords, setCoords] = useState<{ x: number; y: number } | null>(null);

  const show = () => {
    timer.current = setTimeout(() => {
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const gap = 8;
      const pos: Record<Side, { x: number; y: number }> = {
        top: { x: r.left + r.width / 2, y: r.top - gap },
        bottom: { x: r.left + r.width / 2, y: r.bottom + gap },
        left: { x: r.left - gap, y: r.top + r.height / 2 },
        right: { x: r.right + gap, y: r.top + r.height / 2 },
      };
      setCoords(pos[side]);
    }, delay);
  };
  const hide = () => {
    clearTimeout(timer.current);
    setCoords(null);
  };

  useEffect(() => () => clearTimeout(timer.current), []);

  const translate: Record<Side, string> = {
    top: "translate(-50%, -100%)",
    bottom: "translate(-50%, 0)",
    left: "translate(-100%, -50%)",
    right: "translate(0, -50%)",
  };

  return (
    <>
      <span
        ref={ref}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        style={{ display: "inline-flex" }}
      >
        {children}
      </span>
      {coords &&
        createPortal(
          <div
            role="tooltip"
            style={{
              position: "fixed", left: coords.x, top: coords.y, transform: translate[side],
              zIndex: 10001, background: t.bgElev, color: t.text, border: `1px solid ${t.border}`,
              borderRadius: 5, boxShadow: t.shadow, padding: "4px 8px", fontFamily: t.sans,
              fontSize: 12, whiteSpace: "nowrap", pointerEvents: "none",
            }}
          >
            {label}
          </div>,
          document.body,
        )}
    </>
  );
}
