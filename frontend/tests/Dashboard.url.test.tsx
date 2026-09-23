// grilled-meat finding: the URL is user-editable; junk params must be sanitised, not sent as-is.
import { waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import Dashboard from "../src/pages/Dashboard";
import { fake } from "../mocks/handlers";
import { server } from "../mocks/node";
import { renderAt } from "./render";

it("clamps page_size, allow-lists sort and enum filters from a hand-edited URL", async () => {
  const seen: URLSearchParams[] = [];
  server.use(
    http.get("/api/complaints", ({ request }) => {
      const sp = new URL(request.url).searchParams;
      seen.push(sp);
      return HttpResponse.json(fake.list(sp));
    }),
  );
  renderAt(<Dashboard />, "/dashboard", "/dashboard?page_size=-5&sort=bogus&status=closed&status=open&page=abc");
  await waitFor(() => expect(seen.length).toBeGreaterThan(0));
  const sp = seen.at(-1)!;
  expect(sp.get("page_size")).toBe("20");
  expect(sp.get("sort")).toBe("-created_at");
  expect(sp.get("page")).toBe("1");
  expect(sp.getAll("status")).toEqual(["open"]);
});
