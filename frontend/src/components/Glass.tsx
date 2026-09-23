import type { HTMLAttributes, ReactNode } from "react";

import { spotlight } from "../hooks/motion";

interface Props extends HTMLAttributes<HTMLElement> {
  as?: "section" | "div" | "article" | "aside";
  children: ReactNode;
}

export function Glass({ as: Tag = "section", className = "", children, ...rest }: Props) {
  return (
    <Tag className={`glass ${className}`} onPointerMove={spotlight} data-reveal {...rest}>
      <div className="glass-spot" aria-hidden />
      <div style={{ position: "relative" }}>{children}</div>
    </Tag>
  );
}
