// Resizer — a thin draggable handle for resizing a workbench region. Reports the
// new clamped size to the parent as the pointer drags. `axis` is the drag axis;
// `invert` flips the direction (e.g. a handle on a right-docked panel's left edge,
// where dragging left should grow it).
import { useEffect, useState } from "react";
import { clampSize } from "../../lib/layout";
import { t } from "../../theme";

interface Props {
  axis: "x" | "y";
  invert?: boolean;
  size: number;
  min: number;
  max: number;
  onChange: (size: number) => void;
}

export default function Resizer({ axis, invert, size, min, max, onChange }: Props) {
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!dragging) return;
    const cursor = axis === "x" ? "col-resize" : "row-resize";
    document.body.style.cursor = cursor;
    document.body.style.userSelect = "none";
    return () => { document.body.style.cursor = ""; document.body.style.userSelect = ""; };
  }, [dragging, axis]);

  const onPointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    const start = axis === "x" ? e.clientX : e.clientY;
    const base = size;
    const dir = invert ? -1 : 1;
    setDragging(true);

    const move = (ev: PointerEvent) => {
      const cur = axis === "x" ? ev.clientX : ev.clientY;
      onChange(clampSize(base + (cur - start) * dir, min, max));
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const thickness = 5;
  const base: React.CSSProperties = {
    flexShrink: 0,
    background: dragging ? t.accent : "transparent",
    transition: dragging ? "none" : "background 120ms",
    zIndex: 5,
  };
  const style: React.CSSProperties = axis === "x"
    ? { ...base, width: thickness, cursor: "col-resize", height: "100%" }
    : { ...base, height: thickness, cursor: "row-resize", width: "100%" };

  return (
    <div
      role="separator"
      aria-orientation={axis === "x" ? "vertical" : "horizontal"}
      onPointerDown={onPointerDown}
      onMouseEnter={(e) => { if (!dragging) e.currentTarget.style.background = t.border; }}
      onMouseLeave={(e) => { if (!dragging) e.currentTarget.style.background = "transparent"; }}
      style={style}
    />
  );
}
