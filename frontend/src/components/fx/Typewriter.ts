import { useEffect, useState } from "react";

import { prefersReducedMotion } from "../../hooks/motion";

/** Cycles example strings, typing and deleting them — for an empty, unfocused textarea. */
export function useTypewriter(lines: string[], active: boolean): string {
  const [text, setText] = useState(lines[0] ?? "");
  useEffect(() => {
    if (!active || prefersReducedMotion()) return;
    let line = 0;
    let i = 0;
    let deleting = false;
    let timer = 0;
    const tick = () => {
      const full = lines[line]!;
      i += deleting ? -2 : 1;
      setText(full.slice(0, Math.max(0, i)) + "▍");
      let wait = deleting ? 18 : 38;
      if (!deleting && i >= full.length) {
        deleting = true;
        wait = 1800;
      } else if (deleting && i <= 0) {
        deleting = false;
        line = (line + 1) % lines.length;
        wait = 300;
      }
      timer = window.setTimeout(tick, wait);
    };
    timer = window.setTimeout(tick, 600);
    return () => clearTimeout(timer);
  }, [active, lines]);
  return text;
}
