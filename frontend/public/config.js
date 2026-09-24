// Dev default only. In the container this file is overwritten at boot by
// docker-entrypoint.d/10-config.sh from environment variables. Browser-public: never put credentials here.
window.__CIVICPULSE__ = { env: "dev", version: "dev", statsPollMs: 15000, showCacheBadge: true };
