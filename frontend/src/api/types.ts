import type { components, operations } from "./schema";

type S = components["schemas"];
export type Category = S["Category"];
export type Priority = S["Priority"];
export type Status = S["Status"];
export type TriagedBy = S["TriagedBy"];
export type ComplaintCreate = S["ComplaintCreate"];
export type Complaint = S["ComplaintOut"];
export type ComplaintPage = S["ComplaintPage"];
export type StatusUpdate = S["StatusUpdate"];
export type Stats = S["StatsOut"];
export type Providers = S["ProvidersOut"];
export type TriageOutcome = S["TriageOutcome"];
export type ErrorEnvelope = S["ErrorEnvelope"];
export type FieldError = S["FieldError"];
export type ListQuery = NonNullable<operations["list_complaints"]["parameters"]["query"]>;
export type CacheState = "HIT" | "MISS";
