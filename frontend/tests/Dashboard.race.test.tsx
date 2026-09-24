// Found by the browser E2E run: an older, slower list response must not overwrite a newer one.
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";

import Dashboard from "../src/pages/Dashboard";
import { fake } from "../mocks/handlers";
import { server } from "../mocks/node";
import { renderAt } from "./render";

it("ignores a stale list response that arrives after a newer one", async () => {
  server.use(
    http.get("/api/complaints", async ({ request }) => {
      const sp = new URL(request.url).searchParams;
      if (sp.getAll("status").includes("rejected")) await delay(400); // the OLD request is slow
      return HttpResponse.json(fake.list(sp));
    }),
  );
  const user = userEvent.setup();
  renderAt(<Dashboard />, "/dashboard", "/dashboard?status=rejected");
  await user.click(await screen.findByRole("button", { name: "Rejected" })); // newer: no filter, fast
  await waitFor(() => expect(screen.getByText(/Showing 1–20 of 42/)).toBeVisible());
  await new Promise((r) => setTimeout(r, 600)); // let the stale response land
  expect(screen.getByText(/Showing 1–20 of 42/)).toBeVisible();
});
