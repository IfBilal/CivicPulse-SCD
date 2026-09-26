// First-visit intro on the Report page: the heartbeat mark draws itself while the 3D city loads,
// the counter reaches 100 when the city is actually ready, then the mark zooms past the camera
// into orbit. Once per session, skippable (click / key / wheel), never under reduced motion, and
// it gives up waiting after 4 s so a slow GPU never traps anyone on a loading screen.
//
// The exit is CSS-driven, not a JS tween — deliberately (same reasoning as `useReveal`). The exact
// moment the intro finishes is also the moment the city scene is doing the most work (compiling
// shaders, building thousands of instances), which can stall the main thread for a real,
// user-visible stretch. A `gsap.to()` outro tween needs many on-time rAF ticks to reach its end
// state; if the thread is that busy, it can sit part-way through for seconds — during which
// `intro-lock` is still on `<html>`, scroll is still blocked, and the user is stuck looking at a
// half-faded overlay. A CSS transition is scheduled by the browser directly, and — critically —
// interaction is unblocked (`intro-lock` removed, `pointer-events: none` set) the INSTANT `finish()`
// runs, before the fade has even started, so a slow frame never costs the user usable time.
import { useLayoutEffect, useRef, useState } from "react";

import { prefersReducedMotion } from "../../hooks/motion";

export const INTRO_DONE = "civicpulse:intro-done";
const SEEN = "civicpulse:intro-seen";
const EXIT_MS = 550; // must match .intro.exit's transition-duration below

function seen(): boolean {
  try {
    return sessionStorage.getItem(SEEN) === "1";
  } catch {
    return false;
  }
}

export function Intro() {
  const [show, setShow] = useState(() => typeof window !== "undefined" && !prefersReducedMotion() && !seen());
  const root = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const el = root.current;
    if (!show || !el) return;
    try {
      sessionStorage.setItem(SEEN, "1");
    } catch {
      /* private mode: the intro just replays next time */
    }
    document.documentElement.classList.add("intro-lock");
    const count = el.querySelector<HTMLElement>(".intro-count")!;
    let percent = 0;
    let finished = false;
    let raf = 0;

    // A CSS counter (not a gsap.to on a plain object) — same reasoning as the exit: it must keep
    // advancing even if the main thread is busy, so "0%" never just sits there.
    const start = performance.now();
    const tickCount = (now: number) => {
      const t = Math.min(1, (now - start) / 1600);
      percent = Math.round((1 - (1 - t) ** 3) * 86); // ease-out to 86%, city-ready/finish take it to 100
      count.textContent = String(percent);
      if (!finished) raf = requestAnimationFrame(tickCount);
    };
    raf = requestAnimationFrame(tickCount);

    const finish = () => {
      if (finished) return;
      finished = true;
      cancelAnimationFrame(raf);
      count.textContent = "100";
      // Unblock the app FIRST — before any visual fade — so a slow frame here never costs the
      // user usable time. Only the cosmetic exit is left to CSS/paint scheduling.
      document.documentElement.classList.remove("intro-lock");
      window.dispatchEvent(new Event(INTRO_DONE));
      el.classList.add("exit");
      setTimeout(() => setShow(false), EXIT_MS);
    };

    const minTime = new Promise((r) => setTimeout(r, 1500));
    const cityReady = new Promise((r) => window.addEventListener("civicpulse:city-ready", r, { once: true }));
    const giveUp = new Promise((r) => setTimeout(r, 4000));
    void Promise.race([Promise.all([minTime, cityReady]), giveUp]).then(finish);

    const skip = () => finish();
    window.addEventListener("keydown", skip);
    window.addEventListener("wheel", skip, { passive: true });
    window.addEventListener("touchmove", skip, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("keydown", skip);
      window.removeEventListener("wheel", skip);
      window.removeEventListener("touchmove", skip);
      document.documentElement.classList.remove("intro-lock");
    };
  }, [show]);

  if (!show) return null;
  return (
    <div ref={root} className="intro" role="presentation" onClick={() => window.dispatchEvent(new KeyboardEvent("keydown"))}>
      <svg className="intro-mark" viewBox="0 0 220 80" aria-hidden>
        <defs>
          <linearGradient id="ig" x1="0" x2="1">
            <stop offset="0" stopColor="#22e4ff" />
            <stop offset="1" stopColor="#a26bff" />
          </linearGradient>
        </defs>
        <path pathLength={1} strokeDasharray="1" d="M4 44h52l14-30 22 56 18-40 10 14h96" fill="none" stroke="url(#ig)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="intro-meta">
        <span className="intro-count mono">0</span>
        <span className="intro-label">Tuning into the city…</span>
        <span className="intro-skip">click or scroll to skip</span>
      </div>
    </div>
  );
}
