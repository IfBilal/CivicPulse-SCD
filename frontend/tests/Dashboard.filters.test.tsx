// 04-CONTRACTS §6.3: multi-select filters serialise as REPEATED params, reflected in the URL.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import Dashboard from "../src/pages/Dashboard";
import { fake } from "../mocks/handlers";
import { server } from "../mocks/node";
import { renderAt } from "./render";

it("selecting two statuses requests ?status=open&status=in_progress and keeps it in the URL", async () => {
  const seen: string[] = [];
  server.use(
    http.get("/api/complaints", ({ request }) => {
      seen.push(new URL(request.url).search);
      return HttpResponse.json(fake.list(new URL(request.url).searchParams));
    }),
  );
  const user = userEvent.setup();
  renderAt(<Dashboard />, "/dashboard", "/dashboard");
  await screen.findAllByRole("listitem");

  const filters = within(screen.getByRole("region", { name: "Filters" }));
  await user.click(filters.getByRole("button", { name: "Open" }));
  await user.click(filters.getByRole("button", { name: "In progress" }));
  expect(filters.getByRole("button", { name: "Open" })).toHaveAttribute("aria-pressed", "true");

  await waitFor(() => expect(new URLSearchParams(seen.at(-1)).getAll("status")).toEqual(["open", "in_progress"]));
  expect(seen.at(-1)).toContain("status=open&status=in_progress");
  expect(screen.getByTestId("location")).toHaveTextContent("/dashboard?status=open&status=in_progress");
});
