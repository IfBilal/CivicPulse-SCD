import gsap from "gsap";
import { SplitText } from "gsap/SplitText";
import { useLayoutEffect, useRef } from "react";

import { prefersReducedMotion } from "../hooks/motion";

// Stops along the brand gradient (#22e4ff → #6f8bff → #a26bff) for per-character colour while the
// characters are split (a clipped text gradient can't survive per-glyph transforms).
const STOPS: [number, number, number][] = [
  [34, 228, 255],
  [111, 139, 255],
  [162, 107, 255],
];
function gradAt(t: number): string {
  const seg = t < 0.5 ? 0 : 1;
  const k = seg === 0 ? t / 0.5 : (t - 0.5) / 0.5;
  const [a, b] = [STOPS[seg]!, STOPS[seg + 1]!];
  return `rgb(${a.map((v, i) => Math.round(v + (b[i]! - v) * k)).join(",")})`;
}

/** Heading text whose characters rise out of a mask on mount (GSAP SplitText), then revert to
 *  plain text — screen readers and reduced-motion users just get the words. */
export function SplitTitle({ text, className = "grad" }: { text: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;
    gsap.registerPlugin(SplitText);
    el.classList.add("split-live");
    const split = SplitText.create(el, { type: "chars", mask: "chars", aria: "auto" });
    split.chars.forEach((c, i) => ((c as HTMLElement).style.color = gradAt(i / Math.max(1, split.chars.length - 1))));
    const tween = gsap.from(split.chars, {
      yPercent: 100,
      rotateX: -110,
      z: -60,
      transformOrigin: "50% 100% -20px",
      opacity: 0,
      stagger: 0.035,
      duration: 0.9,
      ease: "expo.out",
      onComplete: () => {
        split.revert();
        el.classList.remove("split-live");
      },
    });
    return () => {
      tween.kill();
      split.revert();
      el.classList.remove("split-live");
    };
  }, [text]);
  return (
    <span ref={ref} className={className}>
      {text}
    </span>
  );
}
