// The "city pulse" background: a perspective grid of light points (a night-time city seen from
// above) with shock-wave rings that ripple out whenever a complaint is filed. Lazy-loaded, WebGL-
// guarded, paused when the tab is hidden, and a single static frame under reduced motion.
import { useEffect, useRef } from "react";
import * as THREE from "three";

import { prefersReducedMotion } from "../hooks/motion";
import { PULSE_EVENT } from "../lib/pulse";


const MAX_RINGS = 6;

const vertex = /* glsl */ `
  uniform float uTime;
  uniform vec4 uRings[${MAX_RINGS}];      // xz origin, start time, strength
  uniform vec3 uRingColors[${MAX_RINGS}];
  uniform vec2 uPointer;
  varying vec3 vColor;
  varying float vAlpha;

  void main() {
    vec3 p = position;
    float d = length(p.xz);
    float h = sin(p.x * 0.35 + uTime * 0.6) * 0.25 + cos(p.z * 0.3 + uTime * 0.4) * 0.25;
    h += sin(d * 0.6 - uTime * 1.4) * 0.12;
    vec3 col = mix(vec3(0.13, 0.89, 1.0), vec3(0.64, 0.42, 1.0), smoothstep(-20.0, 30.0, p.x + p.z * 0.4));
    float glow = 0.0;
    for (int i = 0; i < ${MAX_RINGS}; i++) {
      vec4 r = uRings[i];
      float age = uTime - r.z;
      if (r.w > 0.0 && age > 0.0 && age < 5.0) {
        float rd = length(p.xz - r.xy);
        float front = age * 11.0;
        float band = exp(-pow((rd - front) * 0.45, 2.0)) * (1.0 - age / 5.0) * r.w;
        h += band * 2.2;
        glow += band;
        col = mix(col, uRingColors[i], clamp(band, 0.0, 1.0));
      }
    }
    float pd = length(p.xz - uPointer);
    h += exp(-pd * pd * 0.02) * 1.2;
    p.y += h;
    vColor = col;
    vAlpha = clamp(0.25 + h * 0.18 + glow * 0.8, 0.12, 1.0) * smoothstep(70.0, 20.0, d);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = (2.2 + glow * 3.0) * (60.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

const fragment = /* glsl */ `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float r = length(c);
    if (r > 0.5) discard;
    float a = smoothstep(0.5, 0.0, r);
    gl_FragColor = vec4(vColor, a * vAlpha);
  }
`;

function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch {
    return false;
  }
}

export default function PulseField() {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = host.current;
    if (!el || !webglAvailable()) return;
    const reduced = prefersReducedMotion();

    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: "low-power", preserveDrawingBuffer: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(window.innerWidth, window.innerHeight);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x05070f, 0.018);
    const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 200);
    camera.position.set(0, 16, 38);
    camera.lookAt(0, 0, 0);

    const COLS = 150;
    const ROWS = 110;
    const SPACING = 0.9;
    const positions = new Float32Array(COLS * ROWS * 3);
    let k = 0;
    for (let i = 0; i < COLS; i++) {
      for (let j = 0; j < ROWS; j++) {
        // jitter blocks so it reads as a street grid, not a mesh
        const street = i % 10 === 0 || j % 10 === 0 ? 0 : (Math.random() - 0.5) * 0.25;
        positions[k++] = (i - COLS / 2) * SPACING + street;
        positions[k++] = 0;
        positions[k++] = (j - ROWS / 2) * SPACING + street;
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const rings = Array.from({ length: MAX_RINGS }, () => new THREE.Vector4(0, 0, -99, 0));
    const ringColors = Array.from({ length: MAX_RINGS }, () => new THREE.Color("#22e4ff"));
    const uniforms = {
      uTime: { value: 0 },
      uRings: { value: rings },
      uRingColors: { value: ringColors },
      uPointer: { value: new THREE.Vector2(999, 999) },
    };
    const material = new THREE.ShaderMaterial({
      vertexShader: vertex,
      fragmentShader: fragment,
      uniforms,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const points = new THREE.Points(geometry, material);
    scene.add(points);

    const t0 = performance.now();
    let nextRing = 0;
    const addRing = (color: string, strength = 1, x?: number, z?: number) => {
      const r = rings[nextRing % MAX_RINGS]!;
      r.set(x ?? (Math.random() - 0.5) * 50, z ?? (Math.random() - 0.5) * 30, uniforms.uTime.value, strength);
      ringColors[nextRing % MAX_RINGS]!.set(color);
      nextRing += 1;
    };

    const onPulse = (e: Event) => addRing((e as CustomEvent<{ color: string }>).detail?.color ?? "#22e4ff", 1.6, 0, 6);
    window.addEventListener(PULSE_EVENT, onPulse);

    const target = { x: 0, y: 0 };
    const onMove = (e: PointerEvent) => {
      target.x = e.clientX / window.innerWidth - 0.5;
      target.y = e.clientY / window.innerHeight - 0.5;
      uniforms.uPointer.value.set(target.x * 60, target.y * 40 + 6);
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
      if (reduced) renderer.render(scene, camera); // setSize clears the static frame
    };
    window.addEventListener("resize", onResize);

    const ambientColors = ["#168dd9", "#b68b16", "#0da26b", "#d16022", "#9163d5", "#c5547c"];
    let raf = 0;
    let lastAmbient = 0;
    const loop = () => {
      const t = (performance.now() - t0) / 1000;
      uniforms.uTime.value = t;
      if (t - lastAmbient > 2.8) {
        // ambient "complaints" rippling across the city
        addRing(ambientColors[Math.floor(Math.random() * ambientColors.length)]!, 0.6);
        lastAmbient = t;
      }
      camera.position.x += (target.x * 6 - camera.position.x) * 0.03;
      camera.position.y += (16 - target.y * 4 - camera.position.y) * 0.03;
      camera.lookAt(0, 0, 0);
      points.rotation.y = Math.sin(t * 0.05) * 0.08;
      renderer.render(scene, camera);
      raf = requestAnimationFrame(loop);
    };

    const onVisibility = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden && !reduced) raf = requestAnimationFrame(loop);
    };
    document.addEventListener("visibilitychange", onVisibility);

    if (reduced) {
      uniforms.uTime.value = 4;
      renderer.render(scene, camera);
    } else {
      raf = requestAnimationFrame(loop);
    }

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener(PULSE_EVENT, onPulse);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div ref={host} className="bg-canvas" aria-hidden />;
}
