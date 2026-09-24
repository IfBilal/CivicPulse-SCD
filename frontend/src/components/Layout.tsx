import gsap from "gsap";
import { lazy, Suspense, useLayoutEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { runtimeConfig } from "../api/config";
import { prefersReducedMotion } from "../hooks/motion";
import { CursorGlow } from "./fx/CursorGlow";
import { Magnetic } from "./fx/Magnetic";

const PulseField = lazy(() => import("./PulseField"));

const LINKS = [
  { to: "/", label: "Report", end: true },
  { to: "/dashboard", label: "Dashboard", end: false },
  { to: "/stats", label: "Pulse stats", end: false },
];

export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 64 64" aria-hidden>
      <defs>
        <linearGradient id="bm" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#22e4ff" />
          <stop offset="1" stopColor="#a26bff" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="rgba(34,228,255,0.08)" stroke="url(#bm)" strokeWidth="2" />
      <path d="M8 34h12l5-12 8 24 6-16 4 4h13" fill="none" stroke="url(#bm)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Layout() {
  const location = useLocation();
  const nav = useRef<HTMLElement>(null);
  const indicator = useRef<HTMLSpanElement>(null);
  const page = useRef<HTMLDivElement>(null);
  const wipe = useRef<HTMLDivElement>(null);
  const cfg = runtimeConfig();

  // Slide the gradient pill under the active link.
  useLayoutEffect(() => {
    const active = nav.current?.querySelector<HTMLAnchorElement>("a.active");
    const pill = indicator.current;
    if (!pill) return;
    if (!active) {
      gsap.set(pill, { opacity: 0 });
      return;
    }
    const props = { x: active.offsetLeft, width: active.offsetWidth, opacity: 1 };
    if (prefersReducedMotion()) gsap.set(pill, props);
    else gsap.to(pill, { ...props, duration: 0.55, ease: "expo.out" });
  }, [location.pathname]);

  // Page transition on route change.
  useLayoutEffect(() => {
    if (!page.current || prefersReducedMotion()) return;
    const tl = gsap.timeline();
    if (wipe.current) {
      tl.fromTo(wipe.current, { scaleX: 0, transformOrigin: "left center" }, { scaleX: 1, duration: 0.28, ease: "power3.in" })
        .set(wipe.current, { transformOrigin: "right center" })
        .to(wipe.current, { scaleX: 0, duration: 0.42, ease: "power3.out" });
    }
    tl.fromTo(page.current, { opacity: 0, y: 18, filter: "blur(6px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.6, ease: "power3.out", clearProps: "transform,filter" }, 0.2);
    window.scrollTo?.({ top: 0 });
    return () => {
      tl.kill();
    };
  }, [location.pathname]);

  return (
    <>
      <Suspense fallback={null}>
        <PulseField />
      </Suspense>
      <div className="aurora" aria-hidden>
        <span />
        <span />
        <span />
      </div>
      <div className="bg-grain" aria-hidden />
      <CursorGlow />
      <div className="route-wipe" ref={wipe} aria-hidden />
      <div className="shell">
        <header className="topbar">
          <div className="topbar-inner">
            <Magnetic strength={0.25}>
              <NavLink to="/" className="brand" aria-label="CivicPulse home">
                <BrandMark />
                <span className="brand-name">
                  Civic<span>Pulse</span>
                </span>
              </NavLink>
            </Magnetic>
            <nav className="nav" ref={nav} aria-label="Primary">
              <span className="nav-indicator" ref={indicator} aria-hidden />
              {LINKS.map((l) => (
                <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => (isActive ? "active" : "")}>
                  {l.label}
                </NavLink>
              ))}
            </nav>
            <span className="env-chip" title="Runtime config from /config.js">
              env <b>{cfg.env}</b> · {cfg.version.slice(0, 7)}
            </span>
          </div>
        </header>
        <main className="main" id="main">
          <div ref={page} key={location.pathname}>
            <Outlet />
          </div>
        </main>
        <footer className="footer">CivicPulse · complaints triaged by AI, never lost to it · Islamabad / Rawalpindi</footer>
      </div>
    </>
  );
}
