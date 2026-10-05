import { useRef } from "react";

interface Props {
  axis: "x" | "y";
  onDrag: (delta: number) => void;
}

/** A drag handle between two panes, reporting how far it moved in pixels. */
export function Splitter({ axis, onDrag }: Props) {
  const last = useRef(0);
  const at = (event: React.PointerEvent) => (axis === "x" ? event.clientX : event.clientY);
  return (
    // biome-ignore lint/a11y/useFocusableInteractive: resizing is a pointer convenience, the layout works at its default sizes
    <div
      role="separator"
      aria-orientation={axis === "x" ? "vertical" : "horizontal"}
      onPointerDown={(event) => {
        // capture keeps the drag alive when the pointer outruns the handle
        event.currentTarget.setPointerCapture(event.pointerId);
        last.current = at(event);
      }}
      onPointerMove={(event) => {
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
        onDrag(at(event) - last.current);
        last.current = at(event);
      }}
      style={{
        flexShrink: 0,
        cursor: axis === "x" ? "col-resize" : "row-resize",
        touchAction: "none",
        ...(axis === "x"
          ? { width: "5px", borderLeft: "1px solid var(--border)" }
          : { height: "5px", borderTop: "1px solid var(--border)" }),
      }}
    />
  );
}
