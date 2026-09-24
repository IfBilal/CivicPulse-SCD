import gsap from "gsap";
import { useEffect, useRef } from "react";

import { prefersReducedMotion } from "../../hooks/motion";

/** Radial gauge 0–100 %, stroke animated from its previous value. Label carries the number. */
export function Gauge({ value, color = "var(--ok)", label }: { value: number; color?: string; label: string }) {
  const ref = useRef<SVGCircleElement>(null);
  const R = 42;
  const C = 2 * Math.PI * R;
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const target = C * (1 - Math.max(0, Math.min(100, value)) / 100);
    if (prefersReducedMotion()) el.style.strokeDashoffset = String(target);
    else gsap.to(el, { strokeDashoffset: target, duration: 1.6, ease: "expo.out" });
  }, [value, C]);
  return (
    <svg className="gauge" viewBox="0 0 100 100" role="img" aria-label={label}>
      <circle cx="50" cy="50" r={R} className="gauge-track" />
      <circle ref={ref} cx="50" cy="50" r={R} className="gauge-fill" style={{ stroke: color, strokeDasharray: C, strokeDashoffset: C }} />
    </svg>
  );
}
