// Thin typed fetch wrapper over the generated schema (11-FRONTEND.md §4). API errors are handled
// here, never by the error boundary — the boundary only catches render-time crashes.
import { API_BASE } from "./config";
import type {
  CacheState,
  Complaint,
  ComplaintCreate,
  ComplaintPage,
  ErrorEnvelope,
  ListQuery,
  Providers,
  Stats,
  StatusUpdate,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorEnvelope,
  ) {
    super(body.error.message);
    this.name = "ApiError";
  }
}

let lastId: string | null = null;
/** The last X-Request-ID the client saw — the grep-able join key into the backend logs. */
export const lastRequestId = (): string | null => lastId;

function newRequestId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : "00000000-0000-4000-8000-000000000000".replace(/0/g, () => Math.floor(Math.random() * 16).toString(16));
}

function isEnvelope(x: unknown): x is ErrorEnvelope {
  return typeof x === "object" && x !== null && "error" in x && typeof (x as ErrorEnvelope).error?.message === "string";
}

async function request<T>(path: string, init?: RequestInit): Promise<{ data: T; res: Response }> {
  const sent = newRequestId();
  lastId = sent;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "content-type": "application/json", "x-request-id": sent, ...init?.headers },
    });
  } catch {
    throw new ApiError(0, {
      error: { code: "network_error", message: "Can't reach CivicPulse right now. Check your connection and try again.", request_id: sent },
    });
  }
  lastId = res.headers.get("x-request-id") ?? sent;
  const body: unknown = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      res.status,
      isEnvelope(body)
        ? body
        : { error: { code: `http_${res.status}`, message: `The server answered ${res.status} without details.`, request_id: lastId } },
    );
  }
  return { data: body as T, res };
}

/** Repeated params for multi-value filters: ?status=open&status=in_progress (04-CONTRACTS §6.3). */
export function toSearchParams(q: ListQuery): URLSearchParams {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(q)) {
    if (value === undefined || value === null) continue;
    for (const v of Array.isArray(value) ? value : [value]) sp.append(key, String(v));
  }
  return sp;
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

export const api = {
  createComplaint: async (body: ComplaintCreate) =>
    (await request<Complaint>("/complaints", { method: "POST", ...json(body) })).data,
  listComplaints: async (q: ListQuery = {}) => {
    const qs = toSearchParams(q).toString();
    return (await request<ComplaintPage>(`/complaints${qs ? `?${qs}` : ""}`)).data;
  },
  getComplaint: async (id: string) => (await request<Complaint>(`/complaints/${encodeURIComponent(id)}`)).data,
  updateStatus: async (id: string, body: StatusUpdate) =>
    (await request<Complaint>(`/complaints/${encodeURIComponent(id)}/status`, { method: "PATCH", ...json(body) })).data,
  getStats: async (): Promise<{ data: Stats; cache: CacheState | null }> => {
    const { data, res } = await request<Stats>("/stats");
    const h = res.headers.get("x-cache");
    return { data, cache: h === "HIT" || h === "MISS" ? h : null };
  },
  getProviders: async () => (await request<Providers>("/meta/providers")).data,
};
