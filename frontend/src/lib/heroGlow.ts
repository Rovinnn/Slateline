import { useState, type CSSProperties, type MouseEvent } from "react";

/**
 * Cursor-tracking radial glow behind a hero container — a subtle spotlight
 * that follows the pointer, part of the cinematic UI pass. Returns mouse
 * handlers plus the CSS for a fixed, viewport-sized overlay div.
 *
 * The caller's outer element carries the mouse handlers, an overlay div using
 * `style` needs `position: fixed; inset: 0; pointer-events: none`, and the actual
 * content needs `position: relative; z-index: 1` so the glow sits behind it.
 */
export function useHeroGlow() {
  const [pos, setPos] = useState({ x: 0, y: 0, on: false });

  function onMove(e: MouseEvent<HTMLElement>) {
    setPos({ x: e.clientX, y: e.clientY, on: true });
  }

  function onLeave() {
    setPos((p) => ({ ...p, on: false }));
  }

  const style: CSSProperties = {
    transition: "opacity 300ms ease",
    opacity: pos.on ? 1 : 0,
    background: `radial-gradient(circle 70vmax at ${pos.x}px ${pos.y}px, rgba(45,212,191,0.14), rgba(251,191,36,0.07) 45%, transparent 72%)`,
  };

  return { onMove, onLeave, style };
}
