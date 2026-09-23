import gsap from "gsap";
import { useLayoutEffect, useRef, useState, useEffect, type RefObject } from "react";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : true;
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  return reduced;
}

/** Staggered entrance for every `[data-reveal]` inside the scope. Cleaned up via gsap.context. */
export function useReveal<T extends HTMLElement>(deps: unknown[] = []): RefObject<T> {
  const ref = useRef<T>(null);
  useLayoutEffect(() => {
    if (!ref.current || prefersReducedMotion()) return;
    const ctx = gsap.context(() => {
      gsap.from("[data-reveal]", { y: 24, opacity: 0, filter: "blur(6px)", duration: 0.7, ease: "expo.out", stagger: 0.06, clearProps: "filter" });
    }, ref);
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return ref;
}

/** Pointer-follow spotlight on glass cards (sets --mx/--my). */
export function spotlight(e: React.PointerEvent<HTMLElement>): void {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
}
