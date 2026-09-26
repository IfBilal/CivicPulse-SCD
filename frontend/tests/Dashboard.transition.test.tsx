// 00-SPEC §2.2 / Rubric B: an invalid transition surfaces the server's 409 message VERBATIM.
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import Dashboard from "../src/pages/Dashboard";
import { fake } from "../mocks/handlers";
import { server } from "../mocks/node";
import { renderAt } from "./render";

const MESSAGE = "Invalid status transition: resolved -> in_progress. 'resolved' is terminal.";

it("surfaces the server's 409 message verbatim and then locks the terminal complaint", async () => {
  const target = { ...fake.rows[0]!, status: "resolved" as const };
  server.use(
    http.get("/api/complaints", () => HttpResponse.json({ items: [target], total: 1, page: 1, page_size: 20, pages: 1, filters_applied: {} })),
    http.patch("/api/complaints/:id/status", () =>
      HttpResponse.json(
        { error: { code: "invalid_status_transition", message: MESSAGE, request_id: "r", details: { from: "resolved", to: "in_progress", terminal: true } } },
        { status: 409 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderAt(<Dashboard />, "/dashboard", "/dashboard");

  await user.click(await screen.findByRole("button", { expanded: false }));
  const group = screen.getByRole("group", { name: "Move to status" });
  await user.click(within(group).getByRole("button", { name: /in progress/i }));

  expect(await screen.findByText(MESSAGE)).toBeVisible();
  for (const b of within(group).getAllByRole("button")) {
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("title", MESSAGE);
  }
});
