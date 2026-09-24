// Deterministic procedural city, shared by the WebGL scene and the HTML overlays anchored to it.
// Seeded, so every visit (and every test/screenshot) sees the same skyline.
import type { Category } from "../api/types";

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const CITY_RADIUS = 190;
export const BLOCK = 16; // block pitch (street centre to street centre)
export const STREET = 5.5; // street width
export const AVENUE_HALF = 7; // the empty main avenue along z, where the camera flies

export interface Building {
  x: number;
  z: number;
  w: number;
  d: number;
  h: number;
  seed: number;
}

export interface Beacon {
  x: number;
  z: number;
  h: number; // top of the building it stands on
  category: Category;
}

export interface Lane {
  axis: "x" | "z";
  at: number; // the fixed coordinate of the lane
  dir: 1 | -1;
}

export function buildCity(density = 1): { buildings: Building[]; lamps: Float32Array; lanes: Lane[] } {
  const rnd = mulberry32(1947);
  const buildings: Building[] = [];
  const lampPts: number[] = [];
  const n = Math.ceil(CITY_RADIUS / BLOCK);
  const lot = BLOCK - STREET;

  for (let bx = -n; bx < n; bx++) {
    for (let bz = -n; bz < n; bz++) {
      const cx = bx * BLOCK + BLOCK / 2;
      const cz = bz * BLOCK + BLOCK / 2;
      const r = Math.hypot(cx, cz);
      if (r > CITY_RADIUS) continue;
      // galaxy-like disc: dense core, thinning spiral-ish edge
      const edge = r / CITY_RADIUS;
      const arm = 0.5 + 0.5 * Math.sin(Math.atan2(cz, cx) * 3 + edge * 6);
      if (rnd() > (1 - edge * 0.85) * (0.55 + 0.45 * arm) * density + 0.12) continue;
      if (Math.abs(cx) < AVENUE_HALF + lot / 2) continue; // keep the avenue open

      const downtown = Math.exp(-(r * r) / (2 * 70 * 70));
      const parts = rnd() < 0.55 ? 1 : rnd() < 0.7 ? 2 : 4;
      const split = parts === 1 ? 1 : 2;
      const sub = lot / split;
      for (let i = 0; i < parts; i++) {
        const ox = parts === 1 ? 0 : ((i % 2) - 0.5) * sub;
        const oz = parts === 4 ? (Math.floor(i / 2) - 0.5) * sub : parts === 2 ? 0 : 0;
        const w = (parts === 1 ? lot : sub) * (0.72 + rnd() * 0.22);
        const d = (parts === 4 ? sub : lot) * (0.72 + rnd() * 0.22);
        const base = 4 + Math.pow(rnd(), 2.2) * 26;
        const h = base + downtown * (18 + Math.pow(rnd(), 1.6) * 78);
        buildings.push({ x: cx + ox, z: cz + oz, w, d, h, seed: rnd() });
      }
    }
  }

  // street lamps along every street line inside the disc
  for (let s = -n; s <= n; s++) {
    const line = s * BLOCK;
    for (let t = -CITY_RADIUS; t <= CITY_RADIUS; t += 4) {
      if (Math.hypot(line, t) < CITY_RADIUS) lampPts.push(line, 0.05, t);
      if (Math.hypot(t, line) < CITY_RADIUS) lampPts.push(t, 0.05, line);
    }
  }
  // the avenue gets a denser double row of lamps — it's the runway for the fly-through
  for (let t = -CITY_RADIUS; t <= CITY_RADIUS; t += 2.5) {
    lampPts.push(-AVENUE_HALF + 1, 0.05, t, AVENUE_HALF - 1, 0.05, t);
  }

  const lanes: Lane[] = [];
  for (let s = -n + 1; s < n; s++) {
    lanes.push({ axis: "z", at: s * BLOCK - 1.2, dir: 1 }, { axis: "z", at: s * BLOCK + 1.2, dir: -1 });
    lanes.push({ axis: "x", at: s * BLOCK - 1.2, dir: 1 }, { axis: "x", at: s * BLOCK + 1.2, dir: -1 });
  }
  lanes.push({ axis: "z", at: -2.2, dir: -1 }, { axis: "z", at: 2.2, dir: 1 });

  return { buildings, lamps: new Float32Array(lampPts), lanes };
}

/** Complaint beacons along the fly-through avenue — the holograms float above these. */
export const BEACONS: Beacon[] = [
  { x: -22, z: 200, h: 30, category: "water" },
  { x: 24, z: 160, h: 42, category: "electricity" },
  { x: -26, z: 118, h: 52, category: "roads" },
  { x: 22, z: 74, h: 60, category: "sanitation" },
  { x: -24, z: 30, h: 56, category: "streetlights" },
  { x: 26, z: -14, h: 48, category: "other" },
  { x: -22, z: -60, h: 44, category: "water" },
  { x: 24, z: -108, h: 38, category: "roads" },
  { x: -20, z: -158, h: 34, category: "electricity" },
  { x: 22, z: -206, h: 30, category: "sanitation" },
];

/** Camera path (position + look target) keyed by journey progress 0..1. */
export const CAMERA_PATH: { p: number; pos: [number, number, number]; look: [number, number, number] }[] = [
  { p: 0.0, pos: [0, 640, 90], look: [0, 0, 0] }, // orbit: the city as a galaxy of lights
  { p: 0.1, pos: [0, 460, 280], look: [0, 0, 20] }, // descent begins, into the haze
  { p: 0.2, pos: [0, 260, 300], look: [0, 10, 60] },
  { p: 0.3, pos: [0, 110, 280], look: [0, 20, 120] },
  { p: 0.38, pos: [0, 30, 250], look: [0, 16, 180] }, // street level, entering the avenue north end
  { p: 0.46, pos: [0, 13, 190], look: [0, 15, 60] }, // low and close — the deep fly-through begins
  { p: 0.55, pos: [0, 11, 110], look: [0, 14, -30] },
  { p: 0.64, pos: [0, 12, 20], look: [0, 15, -140] },
  { p: 0.73, pos: [0, 13, -70], look: [0, 15, -230] },
  { p: 0.82, pos: [0, 15, -160], look: [0, 16, -300] }, // still deep, still close to the buildings
  { p: 0.9, pos: [50, 90, -230], look: [0, 12, -120] }, // rising out, turning back over the city
  { p: 1.0, pos: [180, 200, -30], look: [0, 0, 0] }, // calm aerial — where the app lives
];
