// Validation bounds and enum members read from the GENERATED OpenAPI document (copied here by
// `make gen-client`). The client-side mirror of the server's rules is therefore generated, not
// hand-typed — it cannot drift from the backend (00-SPEC §2.1 "mirrors without replacing").
import openapi from "./openapi.json";
import type { Category, Priority, Status } from "./types";

interface Prop {
  minLength?: number;
  maxLength?: number;
  anyOf?: Prop[];
}

const schemas = openapi.components.schemas;
const create = schemas.ComplaintCreate.properties as Record<string, Prop>;

function bound(prop: Prop | undefined, key: "minLength" | "maxLength"): number {
  const v = prop?.[key] ?? prop?.anyOf?.find((p) => p[key] !== undefined)?.[key];
  if (v === undefined) throw new Error(`openapi.json is missing ${key} — re-run make gen-client`);
  return v;
}

export const LIMITS = {
  text: { min: bound(create.text, "minLength"), max: bound(create.text, "maxLength") },
  location: { min: bound(create.location, "minLength"), max: bound(create.location, "maxLength") },
  contact: { max: bound(create.reporter_contact, "maxLength") },
  pageSizeMax: (() => {
    const p = openapi.paths["/api/complaints"].get.parameters.find((x) => x.name === "page_size");
    const max = (p?.schema as { maximum?: number } | undefined)?.maximum;
    if (max === undefined) throw new Error("openapi.json is missing page_size maximum");
    return max;
  })(),
} as const;

export const CATEGORIES = schemas.Category.enum as Category[];
export const PRIORITIES = schemas.Priority.enum as Priority[];
export const STATUSES = schemas.Status.enum as Status[];
