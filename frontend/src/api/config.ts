// The exact line guaranteeing build-once-deploy-many (00-SPEC §5.2 q3, ADR-0002): the API is
// always same-origin behind the nginx `/api` proxy, so no environment can bake a URL into the bundle.
export const API_BASE = "/api";

export interface RuntimeConfig {
  env: string;
  version: string;
  statsPollMs: number;
  showCacheBadge: boolean;
}

declare global {
  interface Window {
    __CIVICPULSE__?: Partial<RuntimeConfig>;
  }
}

const DEFAULTS: RuntimeConfig = { env: "dev", version: "dev", statsPollMs: 15000, showCacheBadge: true };

/** Non-URL runtime flags from /config.js (written at container start). Typed defaults if absent. */
export function runtimeConfig(): RuntimeConfig {
  return { ...DEFAULTS, ...(typeof window !== "undefined" ? window.__CIVICPULSE__ : undefined) };
}
