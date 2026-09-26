// Tiny event bus so any page can ripple the background without importing three.js.
export const PULSE_EVENT = "civicpulse:pulse";

export interface PulseOptions {
  /** 0.3 = a faint beacon, 1 = normal, 1.6 = a headline event. */
  strength?: number;
  /** Where on the city grid; omitted = centre stage for strong pulses, random for weak ones. */
  at?: "centre" | "random";
}

export function emitPulse(color = "#22e4ff", opts: PulseOptions = {}): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(PULSE_EVENT, { detail: { color, ...opts } }));
}
