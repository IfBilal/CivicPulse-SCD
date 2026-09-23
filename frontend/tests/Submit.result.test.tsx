// 11-FRONTEND §3.1: render category, priority, summary AND provider — the fallback is user-visible.
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import type { Complaint } from "../src/api/types";
import Submit from "../src/pages/Submit";
import { server } from "../mocks/node";
import { renderAt } from "./render";

const row: Complaint = {
  id: "0f0f0f0f-4c1a-4b0e-9d2f-000000000001", text: "Transformer sparking every evening near the school",
  location: "Gujar Khan", reporter_contact: null, category: "electricity", priority: "high", status: "open",
  ai_summary: null, triaged_by: "rules:fallback", triage_latency_ms: 10031, triage_confidence: null,
  created_at: "2026-09-23T09:00:00Z", updated_at: "2026-09-23T09:00:00Z",
};

it("shows the outlined fallback badge with its explanation when triage degraded to rules", async () => {
  server.use(http.post("/api/complaints", () => HttpResponse.json(row, { status: 201 })));
  const user = userEvent.setup();
  renderAt(<Submit />);
  await user.type(screen.getByLabelText(/what's the problem/i), row.text);
  await user.type(screen.getByLabelText(/where/i), row.location);
  await user.click(screen.getByRole("button", { name: /submit report/i }));

  const badge = (await screen.findByTestId("result")).querySelector('[data-provider="rules:fallback"]');
  expect(badge).toHaveClass("outline");
  expect(badge).toHaveAttribute("title", "AI provider unavailable; classified by keyword rules");
  expect(screen.getByText("Electricity")).toBeVisible();
  expect(screen.getByText("High")).toBeVisible();
});
