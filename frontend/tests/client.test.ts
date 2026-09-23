// The ONLY status knowledge in frontend/src is which statuses exist; transitions are asked, not
// assumed (CLAUDE.md HARD rule 9). Also pins repeated-param serialisation.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { ApiError, api, toSearchParams } from "../src/api/client";

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => (statSync(join(dir, f)).isDirectory() ? files(join(dir, f)) : [join(dir, f)]));
}

it("frontend/src contains no transition table", () => {
  const leaks = files("src")
    .filter((f) => /\.(ts|tsx)$/.test(f) && !f.endsWith("schema.d.ts"))
    .filter((f) => /in_progress.*resolved|TRANSITIONS|allowedNext/.test(readFileSync(f, "utf8")));
  expect(leaks).toEqual([]);
});

it("serialises multi-value filters as repeated params", () => {
  expect(toSearchParams({ status: ["open", "in_progress"], page: 2 }).toString()).toBe("status=open&status=in_progress&page=2");
});

it("wraps a non-envelope error body into an ApiError with the status", async () => {
  const { server } = await import("../mocks/node");
  const { http, HttpResponse } = await import("msw");
  server.use(http.get("/api/stats", () => new HttpResponse("<html>bad gateway</html>", { status: 502 })));
  await expect(api.getStats()).rejects.toSatisfy((e: unknown) => e instanceof ApiError && e.status === 502);
});
