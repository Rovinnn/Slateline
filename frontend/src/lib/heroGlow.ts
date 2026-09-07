import { useState, type CSSProperties, type MouseEvent } from "react";

/**
 * Cursor-tracking radial glow behind a hero container — a subtle spotlight
 * that follows the pointer, part of the cinematic UI pass. Returns mouse
 * handlers plus the CSS for an absolutely-positioned overlay div.
 *
 * The caller's outer element needs `position: relative` + `overflow: hidden`
 * (with these handlers on it), an overlay div using `style` needs
 * `position: absolute; inset: 0; pointer-events: none`, and the actual
 * content needs `position: relative; z-index: 1` so the glow sits behind it.
 */
export function useHeroGlow() {
  const [pos, setPos] = useState({ x: 50, y: 50, on: false });

  function onMove(e: MouseEvent<HTMLElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    setPos({ x: ((e.clientX - r.left) / r.width) * 100, y: ((e.clientY - r.top) / r.height) * 100, on: true });
  }

  function onLeave() {
    setPos((p) => ({ ...p, on: false }));
  }

  const style: CSSProperties = {
    transition: "opacity 300ms ease",
    opacity: pos.on ? 1 : 0,
    background: `radial-gradient(circle farthest-corner at ${pos.x}% ${pos.y}%, rgba(45,212,191,0.14), rgba(251,191,36,0.07) 45%, transparent 72%)`,
  };

  return { onMove, onLeave, style };
}
