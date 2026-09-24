import gsap from "gsap";
import { useEffect, useRef } from "react";

import { prefersReducedMotion } from "../../hooks/motion";

/** A soft light that trails the pointer (fine pointers only; off under reduced motion). */
export function CursorGlow() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || !window.matchMedia?.("(pointer: fine)").matches) return;
    gsap.set(el, { xPercent: -50, yPercent: -50, opacity: 0 });
    const x = gsap.quickTo(el, "x", { duration: 0.6, ease: "power3.out" });
    const y = gsap.quickTo(el, "y", { duration: 0.6, ease: "power3.out" });
    const move = (e: PointerEvent) => {
      x(e.clientX);
      y(e.clientY);
      gsap.to(el, { opacity: 1, duration: 0.4, overwrite: "auto" });
    };
    const leave = () => gsap.to(el, { opacity: 0, duration: 0.4 });
    const down = () => gsap.fromTo(el, { scale: 0.7 }, { scale: 1, duration: 0.6, ease: "elastic.out(1, 0.4)" });
    window.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    window.addEventListener("pointerdown", down);
    return () => {
      window.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
      window.removeEventListener("pointerdown", down);
    };
  }, []);
  return <div ref={ref} className="cursor-glow" aria-hidden />;
}
