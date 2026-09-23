import { useEffect, useState } from "react";

import { prefersReducedMotion } from "../hooks/motion";

const GLYPHS = "!<>-_\\/[]{}—=+*^?#01";

/** Cyberpunk "decode" reveal. The accessible name is always the final text (aria-label). */
export function DecodeText({ text, className }: { text: string; className?: string }) {
  const [reduced] = useState(prefersReducedMotion);
  const [shown, setShown] = useState("");
  useEffect(() => {
    if (reduced) return;
    let frame = 0;
    let raf = 0;
    const total = text.length * 2 + 12;
    const tick = () => {
      frame += 1;
      const settled = Math.floor((frame / total) * text.length * 1.1);
      setShown(
        text
          .split("")
          .map((ch, i) => (i < settled || ch === " " ? ch : GLYPHS[Math.floor(Math.random() * GLYPHS.length)]))
          .join(""),
      );
      if (settled < text.length) raf = requestAnimationFrame(tick);
      else setShown(text);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, reduced]);
  return (
    <span className={className} aria-label={text}>
      <span aria-hidden>{reduced ? text : shown || " "}</span>
    </span>
  );
}
