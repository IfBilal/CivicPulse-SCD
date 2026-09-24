import gsap from "gsap";

import { prefersReducedMotion } from "../../hooks/motion";

/** Particle burst from a point — used when a complaint is filed. Self-cleaning DOM nodes. */
export function burst(x: number, y: number, colors: string[], count = 28): void {
  if (prefersReducedMotion() || typeof document === "undefined") return;
  const layer = document.createElement("div");
  layer.className = "burst-layer";
  layer.setAttribute("aria-hidden", "true");
  document.body.appendChild(layer);
  const tl = gsap.timeline({ onComplete: () => layer.remove() });
  for (let i = 0; i < count; i++) {
    const p = document.createElement("span");
    p.className = "burst-dot";
    p.style.background = colors[i % colors.length]!;
    p.style.left = `${x}px`;
    p.style.top = `${y}px`;
    layer.appendChild(p);
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4;
    const dist = 80 + Math.random() * 140;
    tl.fromTo(
      p,
      { x: 0, y: 0, scale: 1, opacity: 1 },
      { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist + 40, scale: 0, opacity: 0, duration: 0.9 + Math.random() * 0.5, ease: "power3.out" },
      0,
    );
  }
}
