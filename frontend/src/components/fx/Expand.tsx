import gsap from "gsap";
import { useLayoutEffect, useRef, type HTMLAttributes } from "react";

import { prefersReducedMotion } from "../../hooks/motion";

/** Height-animated disclosure body (auto height, so no hard-coded sizes). */
export function Expand({ children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (!ref.current || prefersReducedMotion()) return;
    const tween = gsap.from(ref.current, { height: 0, opacity: 0, duration: 0.5, ease: "power3.out", clearProps: "height,opacity" });
    const kids = gsap.from(ref.current.children, { y: 10, opacity: 0, stagger: 0.06, duration: 0.45, delay: 0.1, ease: "power3.out", clearProps: "all" });
    return () => {
      tween.kill();
      kids.kill();
    };
  }, []);
  return (
    <div ref={ref} style={{ overflow: "hidden" }} {...rest}>
      {children}
    </div>
  );
}
