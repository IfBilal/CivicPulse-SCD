// The living city behind every page. One WebGL context, everything instanced:
//   stars · haze · ~1.3k buildings (procedural windows in-shader) · street lamps (ripple on
//   events) · light-trail traffic (moved entirely on the GPU) · complaint beacons.
// On the Report page the camera is driven by the scroll journey (orbit → descent → avenue
// fly-through → calm aerial); everywhere else it drifts in a slow, calm orbit so data pages stay
// readable. Lazy-loaded, WebGL-guarded, paused when hidden, one static frame under reduced motion,
// and it sheds detail automatically on slow devices.
import { useEffect, useRef } from "react";
import * as THREE from "three";

import { prefersReducedMotion } from "../hooks/motion";
import { journey } from "../lib/journey";
import { PULSE_EVENT } from "../lib/pulse";
import { BEACONS, buildCity, CAMERA_PATH, CITY_RADIUS } from "./layout";

const FOG = new THREE.Color("#05070f");
const CAT_HEX: Record<string, string> = {
  water: "#168dd9",
  electricity: "#e0ad2a",
  sanitation: "#19c27f",
  roads: "#e0702c",
  streetlights: "#a57bff",
  other: "#e0608f",
};
const MAX_RINGS = 6;

const FOG_GLSL = /* glsl */ `
  uniform float uFog;
  float fogAmount(float depth) { return 1.0 - exp(-uFog * uFog * depth * depth); }
`;

const buildingVert = /* glsl */ `
  attribute float aSeed;
  varying vec3 vLocal; varying vec3 vScale; varying vec3 vN; varying float vSeed; varying float vDepth;
  void main() {
    vScale = vec3(length(instanceMatrix[0].xyz), length(instanceMatrix[1].xyz), length(instanceMatrix[2].xyz));
    vLocal = position; vN = normal; vSeed = aSeed;
    vec4 mv = viewMatrix * modelMatrix * instanceMatrix * vec4(position, 1.0);
    vDepth = -mv.z;
    gl_Position = projectionMatrix * mv;
  }
`;
const buildingFrag = /* glsl */ `
  uniform float uTime; uniform float uIntensity; uniform vec3 uFogColor; uniform float uCheap;
  ${FOG_GLSL}
  varying vec3 vLocal; varying vec3 vScale; varying vec3 vN; varying float vSeed; varying float vDepth;
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  void main() {
    vec3 col = vec3(0.028, 0.04, 0.085);
    bool side = abs(vN.y) < 0.5;
    // Cheap tier (auto-enabled on a slow device/GPU): skip the per-fragment window hash — the
    // single most expensive part of this shader once thousands of building fragments are on
    // screen during the low-altitude fly-through — and use a flat lit gradient instead.
    if (side && uCheap > 0.5) {
      col += vec3(0.05, 0.08, 0.16) * (0.4 + vLocal.y * 0.6) * (0.5 + 0.5 * sin(vSeed * 30.0));
      col *= uIntensity;
      gl_FragColor = vec4(mix(col, uFogColor, fogAmount(vDepth)), 1.0);
      return;
    }
    if (side) {
      float u = abs(vN.x) > 0.5 ? vLocal.z * vScale.z : vLocal.x * vScale.x;
      float v = vLocal.y * vScale.y;
      vec2 g = vec2(u / 1.5, v / 2.1);
      vec2 f = fract(g);
      float win = step(0.2, f.x) * step(f.x, 0.8) * step(0.3, f.y) * step(f.y, 0.76);
      float h = hash(floor(g) + vSeed * 91.0 + vN.x * 7.0 + vN.z * 13.0);
      float lit = step(0.57, h) * (0.8 + 0.2 * sin(uTime * 0.5 + h * 60.0));
      vec3 wc = h > 0.93 ? vec3(0.45, 0.92, 1.0) : h > 0.86 ? vec3(0.72, 0.56, 1.0) : vec3(1.0, 0.76, 0.46);
      col += win * lit * wc * 0.95;
      col += vec3(0.015, 0.03, 0.07) * vLocal.y;
      col += smoothstep(0.975, 1.0, vLocal.y) * vec3(0.13, 0.89, 1.0) * 0.45; // roof-line glow
    } else {
      col = vec3(0.02, 0.028, 0.055);
    }
    col *= uIntensity;
    gl_FragColor = vec4(mix(col, uFogColor, fogAmount(vDepth)), 1.0);
  }
`;

const lampVert = /* glsl */ `
  uniform float uTime; uniform float uPixelRatio;
  uniform vec4 uRings[${MAX_RINGS}]; uniform vec3 uRingColors[${MAX_RINGS}];
  ${FOG_GLSL}
  varying vec3 vColor; varying float vAlpha;
  void main() {
    vec3 p = position;
    vec3 col = vec3(1.0, 0.72, 0.36);
    float glow = 0.0;
    for (int i = 0; i < ${MAX_RINGS}; i++) {
      vec4 r = uRings[i];
      float age = uTime - r.z;
      if (r.w > 0.0 && age > 0.0 && age < 6.0) {
        float d = length(p.xz - r.xy);
        float band = exp(-pow((d - age * 38.0) * 0.12, 2.0)) * (1.0 - age / 6.0) * r.w;
        glow += band;
        col = mix(col, uRingColors[i], clamp(band * 1.5, 0.0, 1.0));
      }
    }
    vec4 mv = viewMatrix * modelMatrix * vec4(p, 1.0);
    float depth = -mv.z;
    vColor = col;
    vAlpha = (0.55 + glow) * (1.0 - fogAmount(depth));
    gl_PointSize = clamp((1.6 + glow * 5.0) * uPixelRatio * (220.0 / depth), 1.5 * uPixelRatio, 26.0);
    gl_Position = projectionMatrix * mv;
  }
`;
const softPointFrag = /* glsl */ `
  uniform float uIntensity;
  varying vec3 vColor; varying float vAlpha;
  void main() {
    float r = length(gl_PointCoord - 0.5);
    if (r > 0.5) discard;
    gl_FragColor = vec4(vColor, smoothstep(0.5, 0.0, r) * vAlpha * uIntensity);
  }
`;

const trafficVert = /* glsl */ `
  attribute vec4 aLane; // axisIsX, at, dir, kind
  attribute vec2 aMotion; // speed, offset
  uniform float uTime; uniform float uRadius;
  ${FOG_GLSL}
  varying vec3 vColor; varying float vAlpha;
  void main() {
    float L = uRadius * 2.0;
    float s = (mod(aMotion.y + uTime * aMotion.x, L) - uRadius) * aLane.z;
    vec3 local = position;
    vec3 w = aLane.x < 0.5 ? vec3(aLane.y, 0.45, s) + local : vec3(s, 0.45, aLane.y) + vec3(local.z, local.y, local.x);
    vec4 mv = viewMatrix * modelMatrix * vec4(w, 1.0);
    vColor = aLane.w < 0.5 ? vec3(1.0, 0.93, 0.78) : vec3(1.0, 0.25, 0.35);
    vAlpha = step(length(w.xz), uRadius - 4.0) * (1.0 - fogAmount(-mv.z));
    gl_Position = projectionMatrix * mv;
  }
`;
const flatFrag = /* glsl */ `
  uniform float uIntensity;
  varying vec3 vColor; varying float vAlpha;
  void main() { gl_FragColor = vec4(vColor * uIntensity, vAlpha); }
`;

const beamVert = /* glsl */ `
  ${FOG_GLSL}
  varying float vY; varying float vFog;
  void main() {
    vY = position.y + 0.5;
    vec4 mv = viewMatrix * modelMatrix * vec4(position, 1.0);
    vFog = fogAmount(-mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;
const beamFrag = /* glsl */ `
  uniform vec3 uColor; uniform float uTime; uniform float uAlpha;
  varying float vY; varying float vFog;
  void main() {
    float a = pow(1.0 - vY, 2.2) * (0.55 + 0.25 * sin(uTime * 2.0 + vY * 20.0));
    gl_FragColor = vec4(uColor, a * uAlpha * (1.0 - vFog));
  }
`;

const starVert = /* glsl */ `
  attribute float aSize; uniform float uTime; uniform float uPixelRatio;
  varying vec3 vColor; varying float vAlpha;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vColor = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.85, 0.7), fract(aSize * 7.0));
    vAlpha = 0.55 + 0.45 * sin(uTime * (0.6 + aSize) + aSize * 40.0);
    gl_PointSize = aSize * uPixelRatio * 1.6;
    gl_Position = projectionMatrix * mv;
  }
`;

const hazeVert = /* glsl */ `
  attribute float aSize; uniform float uPixelRatio;
  varying vec3 vColor; varying float vAlpha;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    float depth = -mv.z;
    vColor = mix(vec3(0.35, 0.3, 0.8), vec3(0.15, 0.6, 0.9), fract(aSize * 3.7));
    vAlpha = 0.07 * smoothstep(8.0, 60.0, depth);
    gl_PointSize = min(aSize * uPixelRatio * (300.0 / depth), 900.0);
    gl_Position = projectionMatrix * mv;
  }
`;

type Vec3 = [number, number, number];
function catmull(p0: number, p1: number, p2: number, p3: number, t: number): number {
  const t2 = t * t;
  const t3 = t2 * t;
  return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
}
function samplePath(p: number, key: "pos" | "look"): Vec3 {
  const K = CAMERA_PATH;
  let i = 0;
  while (i < K.length - 2 && p > K[i + 1]!.p) i++;
  const a = K[i]!;
  const b = K[i + 1]!;
  const u = Math.min(1, Math.max(0, (p - a.p) / (b.p - a.p)));
  const e = u * u * (3 - 2 * u); // ease within each leg
  const P = (j: number) => K[Math.min(K.length - 1, Math.max(0, j))]![key];
  return [0, 1, 2].map((c) => catmull(P(i - 1)[c]!, P(i)[c]!, P(i + 1)[c]!, P(i + 2)[c]!, e)) as Vec3;
}

function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch {
    return false;
  }
}

export default function CityScene() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el || !webglAvailable()) return;
    const reduced = prefersReducedMotion();
    const small = window.innerWidth < 760;

    const renderer = new THREE.WebGLRenderer({ antialias: !small, alpha: true, powerPreference: "high-performance" });
    let pixelRatio = Math.min(window.devicePixelRatio, small ? 1.25 : 1.6);
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.5, 4000);
    const city = new THREE.Group();
    scene.add(city);

    const shared = { uTime: { value: 0 }, uFog: { value: 0.0022 }, uPixelRatio: { value: pixelRatio }, uIntensity: { value: 1 } };
    const disposables: { dispose: () => void }[] = [];
    const track = <T extends { dispose: () => void }>(x: T) => (disposables.push(x), x);

    // ── stars ───────────────────────────────────────────────────────────
    const STAR_N = small ? 900 : 1600;
    const starPos = new Float32Array(STAR_N * 3);
    const starSize = new Float32Array(STAR_N);
    for (let i = 0; i < STAR_N; i++) {
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(Math.random() * 0.9 + 0.1);
      const r = 1400 + Math.random() * 600;
      starPos.set([r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph) - 200, r * Math.sin(ph) * Math.sin(th)], i * 3);
      starSize[i] = 0.6 + Math.pow(Math.random(), 3) * 2.6;
    }
    const starGeo = track(new THREE.BufferGeometry());
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    starGeo.setAttribute("aSize", new THREE.BufferAttribute(starSize, 1));
    const starMat = track(
      new THREE.ShaderMaterial({ vertexShader: starVert, fragmentShader: softPointFrag, uniforms: shared, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }),
    );
    scene.add(new THREE.Points(starGeo, starMat));

    // ── buildings ───────────────────────────────────────────────────────
    const { buildings, lamps, lanes } = buildCity(small ? 0.6 : 1);
    const boxGeo = track(new THREE.BoxGeometry(1, 1, 1));
    boxGeo.translate(0, 0.5, 0);
    boxGeo.setAttribute("aSeed", new THREE.InstancedBufferAttribute(Float32Array.from(buildings, (b) => b.seed), 1));
    const buildingMat = track(
      new THREE.ShaderMaterial({ vertexShader: buildingVert, fragmentShader: buildingFrag, uniforms: { ...shared, uFogColor: { value: FOG }, uCheap: { value: 0 } } }),
    );
    const blocks = new THREE.InstancedMesh(boxGeo, buildingMat, buildings.length);
    const m = new THREE.Matrix4();
    buildings.forEach((b, i) => blocks.setMatrixAt(i, m.compose(new THREE.Vector3(b.x, 0, b.z), new THREE.Quaternion(), new THREE.Vector3(b.w, b.h, b.d))));
    blocks.instanceMatrix.needsUpdate = true;
    blocks.frustumCulled = false;
    city.add(blocks);

    // ── ground + street lamps (they carry the event ripples) ───────────
    const ground = new THREE.Mesh(
      track(new THREE.CircleGeometry(CITY_RADIUS + 40, 64)),
      track(new THREE.MeshBasicMaterial({ color: "#070b18" })),
    );
    ground.rotation.x = -Math.PI / 2;
    city.add(ground);
    const rings = Array.from({ length: MAX_RINGS }, () => new THREE.Vector4(0, 0, -99, 0));
    const ringColors = Array.from({ length: MAX_RINGS }, () => new THREE.Color("#22e4ff"));
    const lampGeo = track(new THREE.BufferGeometry());
    lampGeo.setAttribute("position", new THREE.BufferAttribute(lamps, 3));
    const lampMat = track(
      new THREE.ShaderMaterial({
        vertexShader: lampVert,
        fragmentShader: softPointFrag,
        uniforms: { ...shared, uRings: { value: rings }, uRingColors: { value: ringColors } },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    city.add(new THREE.Points(lampGeo, lampMat));

    // ── traffic: light trails, animated entirely in the vertex shader ───
    const CARS = small ? 180 : 420;
    const carGeo = track(new THREE.BoxGeometry(0.4, 0.25, 2.6));
    const aLane = new Float32Array(CARS * 4);
    const aMotion = new Float32Array(CARS * 2);
    for (let i = 0; i < CARS; i++) {
      const lane = lanes[Math.floor(Math.random() * lanes.length)]!;
      aLane.set([lane.axis === "x" ? 1 : 0, lane.at, lane.dir, lane.dir > 0 ? 0 : 1], i * 4);
      aMotion.set([8 + Math.random() * 14, Math.random() * CITY_RADIUS * 2], i * 2);
    }
    carGeo.setAttribute("aLane", new THREE.InstancedBufferAttribute(aLane, 4));
    carGeo.setAttribute("aMotion", new THREE.InstancedBufferAttribute(aMotion, 2));
    const carMat = track(
      new THREE.ShaderMaterial({
        vertexShader: trafficVert,
        fragmentShader: flatFrag,
        uniforms: { ...shared, uRadius: { value: CITY_RADIUS } },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    );
    const traffic = new THREE.InstancedMesh(carGeo, carMat, CARS);
    traffic.frustumCulled = false;
    city.add(traffic);

    // ── complaint beacons ───────────────────────────────────────────────
    const beamGeo = track(new THREE.CylinderGeometry(0.9, 0.9, 1, 16, 1, true));
    const beamAlpha = { value: 1 };
    const beams = BEACONS.map((b) => {
      const mat = track(
        new THREE.ShaderMaterial({
          vertexShader: beamVert,
          fragmentShader: beamFrag,
          uniforms: { uColor: { value: new THREE.Color(CAT_HEX[b.category]) }, uTime: shared.uTime, uAlpha: beamAlpha, uFog: shared.uFog },
          transparent: true,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
          side: THREE.DoubleSide,
        }),
      );
      const mesh = new THREE.Mesh(beamGeo, mat);
      mesh.scale.set(1, 160, 1);
      mesh.position.set(b.x, b.h + 80, b.z);
      city.add(mesh);
      return mesh;
    });

    // ── haze you fall through during the descent ───────────────────────
    const HAZE = small ? 50 : 100;
    const hazePos = new Float32Array(HAZE * 3);
    const hazeSize = new Float32Array(HAZE);
    for (let i = 0; i < HAZE; i++) {
      const a = Math.random() * Math.PI * 2;
      const r = Math.sqrt(Math.random()) * (CITY_RADIUS + 60);
      hazePos.set([Math.cos(a) * r, 150 + Math.random() * 150, Math.sin(a) * r], i * 3);
      hazeSize[i] = 60 + Math.random() * 110;
    }
    const hazeGeo = track(new THREE.BufferGeometry());
    hazeGeo.setAttribute("position", new THREE.BufferAttribute(hazePos, 3));
    hazeGeo.setAttribute("aSize", new THREE.BufferAttribute(hazeSize, 1));
    const hazeUniforms = { uPixelRatio: shared.uPixelRatio, uIntensity: { value: 1 } };
    const hazeMat = track(
      new THREE.ShaderMaterial({ vertexShader: hazeVert, fragmentShader: softPointFrag, uniforms: hazeUniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }),
    );
    const haze = new THREE.Points(hazeGeo, hazeMat);
    city.add(haze);

    // ── ripples from app events ─────────────────────────────────────────
    let nextRing = 0;
    const addRing = (color: string, strength: number, x?: number, z?: number) => {
      const a = Math.random() * Math.PI * 2;
      const r = Math.sqrt(Math.random()) * CITY_RADIUS * 0.8;
      rings[nextRing % MAX_RINGS]!.set(x ?? Math.cos(a) * r, z ?? Math.sin(a) * r, shared.uTime.value, strength);
      ringColors[nextRing % MAX_RINGS]!.set(color);
      nextRing += 1;
    };
    const lookAt = new THREE.Vector3();
    const onPulse = (e: Event) => {
      const d = (e as CustomEvent<{ color?: string; strength?: number; at?: "centre" | "random" }>).detail ?? {};
      const strength = d.strength ?? 1.4;
      const centre = (d.at ?? (strength >= 1 ? "centre" : "random")) === "centre";
      const local = city.worldToLocal(lookAt.clone());
      addRing(d.color ?? "#22e4ff", strength, centre ? local.x : undefined, centre ? local.z : undefined);
    };
    window.addEventListener(PULSE_EVENT, onPulse);

    // ── input, resize ───────────────────────────────────────────────────
    const pointer = { x: 0, y: 0 };
    const onMove = (e: PointerEvent) => {
      pointer.x = e.clientX / window.innerWidth - 0.5;
      pointer.y = e.clientY / window.innerHeight - 0.5;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      if (reduced) render();
    };
    window.addEventListener("resize", onResize);

    // ── holograms: HTML cards anchored above the beacons ────────────────
    const anchorPos = BEACONS.map((b) => new THREE.Vector3(b.x, b.h + 16, b.z));
    const tmp = new THREE.Vector3();
    let anchors: HTMLElement[] = [];
    let anchorScan = 0;
    const placeAnchors = (visibility: number) => {
      if (anchorScan-- <= 0) {
        anchors = Array.from(document.querySelectorAll<HTMLElement>("[data-anchor]"));
        anchorScan = 30;
      }
      if (!anchors.length) return;
      const W = window.innerWidth;
      const H = window.innerHeight;
      anchors.forEach((a) => {
        const i = Number(a.dataset.anchor);
        const world = city.localToWorld(tmp.copy(anchorPos[i]!));
        const dist = world.distanceTo(camera.position);
        world.project(camera);
        const onScreen = world.z < 1 && Math.abs(world.x) < 1.3 && Math.abs(world.y) < 1.3;
        const near = Math.min(1, Math.max(0, (260 - dist) / 180));
        const o = onScreen ? visibility * near : 0;
        a.style.opacity = o.toFixed(3);
        a.style.visibility = o > 0.01 ? "visible" : "hidden";
        if (o > 0.01) {
          const s = Math.min(1.35, Math.max(0.62, 105 / dist));
          a.style.transform = `translate3d(${((world.x + 1) / 2) * W}px, ${((1 - world.y) / 2) * H}px, 0) translate(-50%, -100%) scale(${s.toFixed(3)})`;
        }
      });
    };

    // ── camera: journey path (Report page) or calm orbit (everywhere else) ─
    const camPos = new THREE.Vector3(...CAMERA_PATH[CAMERA_PATH.length - 1]!.pos);
    let orbit = 0;
    let spin = 0;
    const final = CAMERA_PATH[CAMERA_PATH.length - 1]!.pos;
    const smooth = { p: journey.get() ?? 1 };
    const target = new THREE.Vector3();
    const look = new THREE.Vector3();

    let degradeTier = 0;
    const degradeOnce = () => {
      degradeTier = 1;
      pixelRatio = 1;
      renderer.setPixelRatio(1);
      shared.uPixelRatio.value = 1;
      traffic.count = Math.floor(CARS / 3);
      haze.visible = false;
    };
    const degradeMore = () => {
      degradeTier = 2;
      (buildingMat.uniforms.uCheap as { value: number }).value = 1; // drop the per-fragment windows
      blocks.count = Math.floor(buildings.length * 0.6);
      traffic.count = Math.floor(CARS / 6);
    };

    let last = performance.now();
    // Wall-clock windows, not frame counts: on a struggling device a frame-COUNT threshold can
    // take tens of real seconds to reach, during which the page just looks frozen. Check every
    // ~700ms instead, so it gets lighter within about a second, not eventually.
    let windowStart = performance.now();
    let windowFrames = 0;
    let ambientAt = 0;
    const t0 = performance.now();

    function render() {
      const now = performance.now();
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const t = (now - t0) / 1000;
      shared.uTime.value = reduced ? 20 : t;

      const jp = journey.get();
      const story = jp !== null && document.documentElement.dataset.scene !== "calm";
      smooth.p += ((story ? jp : 1) - smooth.p) * (reduced ? 1 : 0.075);
      const p = smooth.p;
      const settled = !story || p > 0.985; // the calm state the app is used in

      // galaxy spin while in orbit, easing to a stop as you descend
      spin += dt * 0.06 * Math.max(0, 1 - p / 0.3);
      city.rotation.y = spin;

      if (settled) {
        orbit += dt * 0.012; // slow, calm drift
        target.set(final[0], final[1], final[2]).applyAxisAngle(THREE.Object3D.DEFAULT_UP, orbit);
        look.set(0, 0, 0);
      } else {
        orbit = 0;
        target.set(...samplePath(p, "pos"));
        look.set(...samplePath(p, "look"));
      }
      target.x += pointer.x * (settled ? 10 : 4);
      target.y += -pointer.y * (settled ? 6 : 3);
      camPos.lerp(target, reduced ? 1 : settled ? 0.03 : 0.12);
      camera.position.copy(camPos);
      lookAt.lerp(look, reduced ? 1 : 0.12);
      camera.lookAt(lookAt);

      // intensity: full city on the story, dimmer + calmer behind data pages
      const calmPage = document.documentElement.dataset.scene === "calm";
      shared.uIntensity.value += ((calmPage ? 0.55 : 1) - shared.uIntensity.value) * 0.05;
      // thin air in orbit (the city reads as a galaxy of lights), thick haze on the way down
      shared.uFog.value = story ? 0.0009 + Math.sin(Math.min(1, p / 0.42) * Math.PI) * 0.0024 + (p > 0.42 ? 0.0012 : 0) : 0.0021;
      hazeUniforms.uIntensity.value = story ? Math.max(0, 1 - Math.abs(p - 0.18) / 0.16) : 0;
      haze.visible = degradeTier < 1 && hazeUniforms.uIntensity.value > 0.01;
      beamAlpha.value = calmPage ? 0.35 : 1;

      if (t - ambientAt > (settled ? 7 : 2.5)) {
        const b = BEACONS[Math.floor(Math.random() * BEACONS.length)]!;
        addRing(CAT_HEX[b.category]!, settled ? 0.5 : 0.8, b.x, b.z);
        ambientAt = t;
      }
      beams.forEach((beam, i) => (beam.scale.x = beam.scale.z = 1 + 0.25 * Math.sin(t * 2 + i)));

      const holo = story ? Math.min(1, Math.max(0, (p - 0.4) / 0.06)) * Math.min(1, Math.max(0, (0.86 - p) / 0.06)) : 0;
      placeAnchors(holo);

      renderer.render(scene, camera);

      if (degradeTier < 2 && !reduced) {
        windowFrames += 1;
        if (now - windowStart > 700) {
          const fps = (windowFrames * 1000) / (now - windowStart);
          if (degradeTier === 0 && fps < 48) degradeOnce();
          else if (degradeTier === 1 && fps < 40) degradeMore();
          windowStart = now;
          windowFrames = 0;
        }
      }
    }

    let raf = 0;
    let cancelled = false;
    const loop = () => {
      render();
      raf = requestAnimationFrame(loop);
    };
    const onVisibility = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden && !reduced) {
        last = performance.now();
        raf = requestAnimationFrame(loop);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    // Compile every shader (6 distinct programs — buildings, lamps, traffic, beams, stars, haze)
    // BEFORE the render loop starts, via `compileAsync` rather than letting the first `render()`
    // call trigger synchronous compilation. On some GPUs/drivers that first compile is a real,
    // user-visible stall (hundreds of ms to low seconds) — and it used to land in the exact same
    // window as React mounting, fonts loading, and the Report page's GSAP/ScrollTrigger setup,
    // which is what made the site feel "stuck" on a cold tab. `compileAsync` uses
    // KHR_parallel_shader_compile where the browser supports it and otherwise falls back to a
    // normal (still one-time) compile — either way it happens BEFORE the loop starts, isolated
    // from that startup burst, so the first real render is fast.
    const start = () => {
      if (cancelled) return;
      last = performance.now();
      if (reduced) render();
      else raf = requestAnimationFrame(loop);
      window.dispatchEvent(new Event("civicpulse:city-ready"));
    };
    void renderer
      .compileAsync(scene, camera)
      .catch(() => {}) // unsupported/failed compileAsync — fall back to the ordinary (lazy) path
      .then(start);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener(PULSE_EVENT, onPulse);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      disposables.forEach((d) => d.dispose());
      blocks.dispose();
      traffic.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div ref={host} className="bg-canvas" aria-hidden />;
}
