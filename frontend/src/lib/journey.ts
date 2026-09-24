// Shared scroll state between the DOM story (GSAP ScrollTrigger) and the WebGL city camera.
// `null` = no journey on this page → the city sits in its calm aerial orbit.
let progress: number | null = null;

export const journey = {
  get: (): number | null => progress,
  set: (p: number | null): void => {
    progress = p === null ? null : Math.min(1, Math.max(0, p));
  },
};
