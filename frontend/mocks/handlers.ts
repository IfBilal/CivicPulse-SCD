import { delay, http, HttpResponse } from "msw";

import type { ComplaintCreate, ErrorEnvelope, StatusUpdate } from "../src/api/types";
import { FakeServer } from "./fakeServer";

export const fake = new FakeServer();
const rid = (req: Request) => req.headers.get("x-request-id") ?? crypto.randomUUID();
const envelope = (req: Request, status: number, code: string, message: string, extra: Partial<ErrorEnvelope["error"]> = {}) =>
  HttpResponse.json<ErrorEnvelope>({ error: { code, message, request_id: rid(req), ...extra } }, { status, headers: { "x-request-id": rid(req) } });

/** Latency is realistic in the browser (to show the honest loading state) and zero in tests. */
const realistic = (ms: number) => (import.meta.env.MODE === "test" ? delay(0) : delay(ms));

export const handlers = [
  http.post("/api/complaints", async ({ request }) => {
    const body = (await request.json()) as ComplaintCreate;
    const fields = [];
    if ((body.text ?? "").trim().length < 10) fields.push({ field: "text", code: "too_short", message: "String should have at least 10 characters", constraint: { min: 10 } });
    if ((body.location ?? "").trim().length < 3) fields.push({ field: "location", code: "too_short", message: "String should have at least 3 characters", constraint: { min: 3 } });
    if (fields.length) return envelope(request, 400, "validation_error", "Request body failed validation.", { fields });
    const { row, latencyMs } = fake.create(body);
    await realistic(latencyMs);
    return HttpResponse.json(row, { status: 201, headers: { location: `/api/complaints/${row.id}`, "x-request-id": rid(request) } });
  }),

  http.get("/api/complaints", async ({ request }) => {
    await realistic(350);
    return HttpResponse.json(fake.list(new URL(request.url).searchParams), { headers: { "x-request-id": rid(request) } });
  }),

  http.get("/api/complaints/:id", ({ request, params }) => {
    const row = fake.get(String(params.id));
    return row ? HttpResponse.json(row) : envelope(request, 404, "not_found", "Resource not found.");
  }),

  http.patch("/api/complaints/:id/status", async ({ request, params }) => {
    const { status } = (await request.json()) as StatusUpdate;
    await realistic(300);
    const result = fake.transition(String(params.id), status);
    if (!result) return envelope(request, 404, "not_found", "Resource not found.");
    if ("conflict" in result) {
      const { from, allowed } = result.conflict;
      const terminal = allowed.length === 0;
      return envelope(request, 409, "invalid_status_transition",
        `Invalid status transition: ${from} -> ${status}.${terminal ? ` '${from}' is terminal.` : ""}`,
        { details: { from, to: status, allowed_from_current: allowed, terminal } });
    }
    return HttpResponse.json(result.ok);
  }),

  http.get("/api/stats", async ({ request }) => {
    await realistic(250);
    const { data, cache } = fake.stats();
    return HttpResponse.json(data, { headers: { "x-cache": cache, "cache-control": "public, max-age=0, must-revalidate", "x-request-id": rid(request) } });
  }),

  http.get("/api/meta/providers", async () => {
    await realistic(200);
    return HttpResponse.json(fake.providers());
  }),
];
