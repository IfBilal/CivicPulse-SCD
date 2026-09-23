import gsap from "gsap";
import { useEffect, useRef } from "react";

import { prefersReducedMotion } from "../hooks/motion";

export function CountUp({ value, decimals = 0, suffix = "" }: { value: number; decimals?: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const last = useRef(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fmt = (n: number) => `${n.toFixed(decimals)}${suffix}`;
    if (prefersReducedMotion()) {
      el.textContent = fmt(value);
      last.current = value;
      return;
    }
    const obj = { n: last.current };
    const tween = gsap.to(obj, { n: value, duration: 1.2, ease: "power3.out", onUpdate: () => (el.textContent = fmt(obj.n)) });
    last.current = value;
    return () => {
      tween.kill();
    };
  }, [value, decimals, suffix]);
  return <span ref={ref}>{`${value.toFixed(decimals)}${suffix}`}</span>;
}
