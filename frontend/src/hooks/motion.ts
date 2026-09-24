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

/** Staggered entrance for every `[data-reveal]` inside the scope: whatever is on screen animates
 *  in immediately, the rest as it scrolls into view.
 *
 *  IntersectionObserver, not ScrollTrigger — deliberately. `ScrollTrigger.batch` pre-computes each
 *  element's trigger position in absolute page pixels at *setup* time. On a page whose total
 *  height changes drastically after that (the Report page's scroll-driven journey is tall), those
 *  cached positions go stale and the element can be scrolled straight past without ever firing —
 *  leaving it permanently at `opacity: 0`. An observer has no positions to go stale.
 *
 *  A plain CSS `transition`, not a `gsap.to()` tween — also deliberately. A `gsap.to()` tween is
 *  driven by JS on every `requestAnimationFrame`; if the main thread is busy (the WebGL city scene
 *  rendering a heavy frame), the tween's own ticks get starved and it can sit frozen mid-fade for
 *  as long as the thread stays busy. A CSS transition is scheduled by the browser's style/
 *  compositor pipeline and reaches its end state reliably regardless of main-thread load — this
 *  was a real bug: the Submit page content behind the 3D city was stuck at opacity 0. */
export function useReveal<T extends HTMLElement>(deps: unknown[] = []): RefObject<T> {
  const ref = useRef<T>(null);
  useLayoutEffect(() => {
    if (!ref.current || prefersReducedMotion()) return;
    const root = ref.current;

    const arm = (el: Element) => {
      if (el.hasAttribute("data-reveal-armed")) return;
      el.setAttribute("data-reveal-armed", "1");
      el.classList.add("reveal-hidden");
    };
    const reveal = (el: Element) => el.classList.add("reveal-shown");

    root.querySelectorAll("[data-reveal]").forEach(arm);

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          reveal(entry.target);
          io.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.01 },
    );
    root.querySelectorAll("[data-reveal]").forEach((el) => io.observe(el));

    // Elements added later (e.g. the live-report ticker, once its fetch resolves) still get armed
    // and observed: a page's data-reveal set isn't always complete at first paint.
    const mo = new MutationObserver((records) => {
      for (const r of records) {
        r.addedNodes.forEach((node) => {
          if (!(node instanceof Element)) return;
          const targets = node.matches("[data-reveal]") ? [node] : Array.from(node.querySelectorAll("[data-reveal]"));
          targets.forEach((el) => {
            arm(el);
            io.observe(el);
          });
        });
      }
    });
    mo.observe(root, { childList: true, subtree: true });

    return () => {
      io.disconnect();
      mo.disconnect();
    };
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
