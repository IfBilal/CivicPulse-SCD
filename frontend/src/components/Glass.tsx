import gsap from "gsap";
import { useRef, type HTMLAttributes, type PointerEvent, type ReactNode } from "react";

import { prefersReducedMotion, spotlight } from "../hooks/motion";

interface Props extends HTMLAttributes<HTMLElement> {
  as?: "section" | "div" | "article" | "aside";
  /** 3D tilt toward the pointer (cards you look at, not forms you type in). */
  tilt?: boolean;
  children: ReactNode;
}

export function Glass({ as: Tag = "section", className = "", tilt = false, children, ...rest }: Props) {
  const ref = useRef<HTMLElement>(null);
  const move = (e: PointerEvent<HTMLElement>) => {
    spotlight(e);
    if (!tilt || prefersReducedMotion() || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    gsap.to(e.currentTarget, { rotateY: px * 7, rotateX: -py * 7, transformPerspective: 900, duration: 0.6, ease: "power3.out" });
  };
  const leave = (e: PointerEvent<HTMLElement>) => {
    if (tilt) gsap.to(e.currentTarget, { rotateY: 0, rotateX: 0, duration: 0.9, ease: "elastic.out(1, 0.5)" });
  };
  return (
    <Tag ref={ref as never} className={`glass ${tilt ? "tilt" : ""} ${className}`} onPointerMove={move} onPointerLeave={leave} data-reveal {...rest}>
      <div className="glass-spot" aria-hidden />
      <div style={{ position: "relative" }}>{children}</div>
    </Tag>
  );
}
