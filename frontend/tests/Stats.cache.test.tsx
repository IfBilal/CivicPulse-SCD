// 00-SPEC §2.4 / Rubric B: the X-Cache badge — HIT reads "cached N s ago" from cache_age_seconds.
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import Stats from "../src/pages/Stats";
import { fake } from "../mocks/handlers";
import { server } from "../mocks/node";
import { renderAt } from "./render";

it("renders a HIT badge with the server's cache age", async () => {
  const { data } = fake.stats();
  server.use(http.get("/api/stats", () => HttpResponse.json({ ...data, cache_age_seconds: 12 }, { headers: { "X-Cache": "HIT" } })));
  renderAt(<Stats />, "/stats", "/stats");
  const badge = await screen.findByText("cached 12 s ago");
  expect(badge.closest("[data-cache]")).toHaveAttribute("data-cache", "HIT");
});

it("renders a MISS badge as computed just now", async () => {
  renderAt(<Stats />, "/stats", "/stats");
  expect(await screen.findByText("computed just now")).toBeVisible();
});
