// The scroll journey on the Report page. A sticky full-screen stage whose beats overlap, so there
// is always something in front of you while the WebGL camera flies: orbit → descent through the
// haze → down the avenue past complaint holograms → up to a calm aerial view, where the form is.
// Presentation only — it teaches the product's real behaviour (incl. the fallback) and decides
// nothing. Without motion (reduced motion, jsdom) the same markup reads as a static page.
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useLayoutEffect, useRef } from "react";

import { prefersReducedMotion } from "../../hooks/motion";
import { CATEGORY_HEX, CATEGORY_META } from "../../lib/format";
import { journey } from "../../lib/journey";
import { emitPulse } from "../../lib/pulse";
import { BEACONS } from "../../city/layout";
import { INTRO_DONE } from "./Intro";

const TYPED = "Pani ka pipe burst ho gaya hai near the masjid — water on the road since fajr.";
const PROBLEM =
  "A burst pipe. A dead streetlight. Garbage for three days. Every complaint is a signal — and most of them are lost before anyone reads them.";
const STEPS = [
  { k: "01", t: "You report it", d: "In your own words — English, Urdu, or both." },
  { k: "02", t: "AI triages it", d: "Category, priority and a one-line summary, in seconds." },
  { k: "03", t: "It's never lost", d: "If the AI stalls, keyword rules take over — and you're told." },
  { k: "04", t: "The city acts", d: "Open → in progress → resolved. Every step checked by the server." },
];
const HOLOGRAMS = [
  { text: "Pipe burst near the masjid", loc: "G-9/1", pri: "High" },
  { text: "Transformer sparking every evening", loc: "Gujar Khan", pri: "High" },
  { text: "Pothole — two bikes slipped", loc: "F-11 Markaz", pri: "High" },
  { text: "Garbage uncollected for 3 days", loc: "I-8/2", pri: "Normal" },
  { text: "Street dark for a week", loc: "E-11/3", pri: "Normal" },
  { text: "Stray dogs near the school", loc: "G-11/2", pri: "Normal" },
  { text: "Sewage overflow at the hospital gate", loc: "G-8", pri: "High" },
  { text: "Tube well down, whole sector dry", loc: "I-14/3", pri: "High" },
  { text: "Signal dead at the chowk", loc: "10th Avenue", pri: "Normal" },
  { text: "Illegal parking blocks the ambulance bay", loc: "Blue Area", pri: "Normal" },
];

export function Journey() {
  const root = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    if (prefersReducedMotion()) {
      journey.set(1); // calm aerial, no flight
      return () => journey.set(null);
    }
    gsap.registerPlugin(ScrollTrigger);
    el.classList.add("live");
    journey.set(0);

    const ctx = gsap.context(() => {
      // hero entrance waits for the intro to finish (or runs now if there was none)
      const heroIn = gsap.timeline({ paused: true });
      heroIn
        .from(".hero-word", { yPercent: 110, rotateX: -95, z: -140, transformOrigin: "50% 100% -30px", opacity: 0, duration: 1.4, ease: "expo.out", stagger: 0.09 })
        .from(".hero-sub, .hero-cta, .scroll-cue", { y: 24, opacity: 0, duration: 1, ease: "power3.out", stagger: 0.12 }, "-=0.9");
      const playHero = () => heroIn.play();
      if (document.querySelector(".intro")) window.addEventListener(INTRO_DONE, playHero, { once: true });
      else playHero();

      // ── one scrubbed timeline, 0 → 1, shared with the WebGL camera ──────
      const typed = el.querySelector<HTMLElement>(".typed")!;
      const lat = el.querySelector<HTMLElement>(".lat")!;
      const typing = { n: 0 };
      const ms = { v: 0 };
      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: {
          trigger: el,
          start: "top top",
          // A function, not the "bottom bottom" shorthand — computed fresh on every refresh from
          // the element's actual rendered height. The shorthand's own cached/parsed value has been
          // observed to go wildly wrong (~20x too large) after React StrictMode's dev-only double
          // mount/unmount/remount of this effect, which silently breaks the whole journey (the
          // scrub barely advances no matter how far you scroll). Computing it ourselves in plain
          // JS removes any dependency on however that internal cache gets keyed/invalidated.
          end: () => el.offsetHeight - window.innerHeight,
          scrub: 0.8,
          onUpdate: (self) => journey.set(self.progress),
        },
      });
      // things fly TOWARD you as you advance: exits scale up + blur, entries come from depth
      const enter = (sel: string, at: number, d = 0.05) =>
        tl.fromTo(sel, { autoAlpha: 0, scale: 0.55, z: -300, filter: "blur(10px)" }, { autoAlpha: 1, scale: 1, z: 0, filter: "blur(0px)", duration: d, ease: "power2.out" }, at);
      const exit = (sel: string, at: number, d = 0.05) =>
        tl.to(sel, { autoAlpha: 0, scale: 1.9, z: 300, filter: "blur(12px)", duration: d, ease: "power2.in" }, at);

      tl.set({}, {}, 0);
      // 0.00 – 0.13 · orbit: hero
      exit(".beat-hero", 0.08, 0.06);
      // 0.12 – 0.30 · descent through the haze: the numbers
      enter(".stat-1", 0.12);
      exit(".stat-1", 0.19);
      enter(".stat-2", 0.2);
      exit(".stat-2", 0.28);
      // 0.28 – 0.44 · street level: the problem, lit word by word
      enter(".beat-problem", 0.24, 0.04);
      tl.fromTo(".beat-problem .w", { opacity: 0.12 }, { opacity: 1, stagger: 0.006, duration: 0.03 }, 0.26);
      exit(".beat-problem", 0.34, 0.04);
      // 0.44 – 0.86 · the avenue: the complaint's journey, holograms passing by
      enter(".beat-scene", 0.36, 0.04);
      tl.fromTo(".device", { rotateY: -32, rotateX: 10 }, { rotateY: -10, rotateX: 4, duration: 0.05 }, 0.36)
        .to(typing, { n: TYPED.length, duration: 0.1, onUpdate: () => (typed.textContent = TYPED.slice(0, Math.round(typing.n))) }, 0.39)
        .to(".send-btn", { background: "linear-gradient(120deg,#22e4ff,#a26bff)", color: "#041018", duration: 0.01 }, 0.5);
      const caption = (i: number, at: number) =>
        tl
          .to(".caption", { autoAlpha: 0, rotateX: 50, y: -20, transformOrigin: "50% 0%", duration: 0.015 }, at)
          .fromTo(`.caption-${i}`, { autoAlpha: 0, rotateX: -70, y: 24, transformOrigin: "50% 100%" }, { autoAlpha: 1, rotateX: 0, y: 0, duration: 0.02 }, at + 0.01)
          .to(".rail-dot", { background: "rgba(140,170,255,0.25)", scale: 1, duration: 0.01 }, at)
          .to(`.rail-dot-${i}`, { background: "#22e4ff", scale: 1.5, duration: 0.01 }, at);
      tl.set(".caption", { autoAlpha: 0 }, 0.36).set(".caption-0", { autoAlpha: 1 }, 0.36).set(".rail-dot-0", { background: "#22e4ff", scale: 1.5 }, 0.36);
      caption(1, 0.51);
      tl.to(".device", { rotateY: 8, rotateX: 5, duration: 0.05 }, 0.51)
        .fromTo(".beam", { yPercent: -120, opacity: 1 }, { yPercent: 520, duration: 0.06, ease: "power1.inOut" }, 0.52)
        .from(".chip-cat", { rotateY: -180, opacity: 0, duration: 0.02, ease: "back.out(2)" }, 0.56)
        .from(".chip-pri", { rotateY: -180, opacity: 0, duration: 0.02, ease: "back.out(2)" }, 0.565)
        .from(".sum", { opacity: 0, x: -20, duration: 0.025 }, 0.575)
        .from(".badge-ai", { opacity: 0, y: 10, duration: 0.02 }, 0.59)
        .to(ms, { v: 842, duration: 0.04, onUpdate: () => (lat.textContent = `${Math.round(ms.v)} ms`) }, 0.56)
        .call(() => emitPulse(CATEGORY_HEX.water, { strength: 1.2 }), [], 0.6);
      caption(2, 0.64);
      tl.to(".device", { rotateY: -12, rotateX: -3, duration: 0.05 }, 0.64)
        .to(".badge-ai", { rotateX: 90, opacity: 0, duration: 0.02 }, 0.68)
        .fromTo(".badge-fb", { rotateX: -90, opacity: 0 }, { rotateX: 0, opacity: 1, duration: 0.025 }, 0.7, )
        .to(".device", { boxShadow: "0 0 0 1px rgba(255,181,71,0.65), 0 30px 90px -20px rgba(255,181,71,0.4)", duration: 0.02 }, 0.7)
        .call(() => emitPulse("#ffb547", { strength: 1.2 }), [], 0.71);
      caption(3, 0.79);
      tl.to(".device", { rotateY: 0, rotateX: 0, boxShadow: "0 0 0 1px rgba(61,245,166,0.55), 0 30px 90px -20px rgba(61,245,166,0.35)", duration: 0.04 }, 0.79)
        .fromTo(".track-fill", { scaleX: 0 }, { scaleX: 1, duration: 0.07 }, 0.8)
        .to(".st-1", { color: "#ffb547", duration: 0.006 }, 0.825)
        .to(".st-2", { color: "#3df5a6", duration: 0.006 }, 0.86)
        .call(() => emitPulse("#3df5a6", { strength: 1.2 }), [], 0.865);
      exit(".beat-scene", 0.9, 0.05);
      // 0.92 – 1.00 · rising over the city: your turn (then the page calms down)
      enter(".beat-turn", 0.93, 0.05);
      tl.to({}, { duration: 0.05 }, 0.97);
    }, el);

    return () => {
      ctx.revert();
      el.classList.remove("live");
      journey.set(null);
    };
  }, []);

  const toForm = () => document.getElementById("report")?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth" });

  return (
    <div ref={root} className="journey">
      <div className="journey-stage">
        <section className="beat beat-hero" aria-labelledby="hero-title">
          <p className="eyebrow">CivicPulse · Islamabad / Rawalpindi</p>
          <h1 id="hero-title" className="hero-title">
            {["Every", "city", "has", "a"].map((w) => (
              <span key={w} className="mask">
                <span className="hero-word">{w}&nbsp;</span>
              </span>
            ))}
            <span className="mask">
              <span className="hero-word grad">pulse.</span>
            </span>
          </h1>
          <p className="hero-sub">Report a problem in your own words. AI triages it in seconds — and if the AI fails, you are still heard.</p>
          <div className="row hero-cta">
            <button type="button" className="btn btn-primary" onClick={toForm}>
              Report now ↓
            </button>
            <span className="hint">or scroll to fly through the city</span>
          </div>
          <div className="scroll-cue" aria-hidden>
            <span />
          </div>
        </section>

        <section className="beat beat-stat stat-1" aria-label="Scale">
          <p className="stat-big">
            <span className="grad">2 million</span> people.
          </p>
        </section>
        <section className="beat beat-stat stat-2" aria-label="Volume">
          <p className="stat-big">
            A thousand small <span className="grad">emergencies</span> a day.
          </p>
        </section>

        <section className="beat beat-problem" aria-label="The problem">
          <p>
            {PROBLEM.split(" ").map((w, i) => (
              <span key={i} className="w">
                {w}{" "}
              </span>
            ))}
          </p>
        </section>

        <section className="beat beat-scene" aria-label="How a complaint travels">
          <div className="scene-inner">
            <div className="captions">
              <div className="rail" aria-hidden>
                {STEPS.map((_, i) => (
                  <span key={i} className={`rail-dot rail-dot-${i}`} />
                ))}
              </div>
              {STEPS.map((s, i) => (
                <div key={s.k} className={`caption caption-${i}`}>
                  <span className="caption-k">{s.k}</span>
                  <h2>{s.t}</h2>
                  <p>{s.d}</p>
                </div>
              ))}
            </div>
            <div className="device-wrap" aria-hidden>
              <div className="device">
                <div className="device-bar">
                  <span />
                  <span />
                  <span />
                  <em>civicpulse · new report</em>
                </div>
                <div className="device-body">
                  <div className="bubble">
                    <span className="typed">{TYPED}</span>
                    <span className="caret" />
                  </div>
                  <div className="device-meta">
                    <span>📍 Street 12, G-9/1</span>
                    <span className="send-btn">Send ⟶</span>
                  </div>
                  <div className="triage">
                    <div className="beam" />
                    <div className="row">
                      <span className="chip chip-cat" style={{ ["--c" as string]: "var(--cat-water)" }}>
                        <span className="dot" /> Water
                      </span>
                      <span className="chip chip-pri" style={{ ["--c" as string]: "var(--danger)" }}>
                        ▲▲ High
                      </span>
                      <span className="lat mono">842 ms</span>
                    </div>
                    <p className="sum">Burst main flooding Street 12; road under water since dawn.</p>
                    <div className="badges">
                      <span className="badge-provider solid badge-ai">✦ AI · groq</span>
                      <span className="badge-provider outline badge-fb">⚠ Keyword rules (fallback)</span>
                    </div>
                  </div>
                  <div className="track">
                    <div className="track-line">
                      <span className="track-fill" />
                    </div>
                    <div className="track-steps">
                      <span className="st-0">○ Open</span>
                      <span className="st-1">◐ In progress</span>
                      <span className="st-2">✓ Resolved</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="beat beat-turn" aria-label="Your turn">
          <p className="eyebrow">Your turn</p>
          <p className="yt-big">
            Tell the city what&apos;s <span className="grad">broken.</span>
          </p>
          <button type="button" className="btn btn-primary" onClick={toForm}>
            Start your report ↓
          </button>
        </section>

        <button type="button" className="skip-story" onClick={toForm}>
          Skip to report ↓
        </button>
      </div>

      <div className="holograms" aria-hidden>
        {HOLOGRAMS.map((h, i) => {
          const cat = BEACONS[i]!.category;
          return (
            <div key={i} className="holo" data-anchor={i} style={{ ["--c" as string]: CATEGORY_META[cat].color }}>
              <div className="holo-card">
                <div className="holo-top">
                  <span className="dot" />
                  {CATEGORY_META[cat].label}
                  <em>{h.pri}</em>
                </div>
                <p>{h.text}</p>
                <div className="holo-foot">
                  📍 {h.loc} · <b>open</b>
                </div>
              </div>
              <span className="holo-stem" />
            </div>
          );
        })}
      </div>

    </div>
  );
}
