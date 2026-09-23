// Tiny event bus so any page can ripple the background without importing three.js.
export const PULSE_EVENT = "civicpulse:pulse";

export function emitPulse(color = "#22e4ff"): void {
  window.dispatchEvent(new CustomEvent(PULSE_EVENT, { detail: { color } }));
}
