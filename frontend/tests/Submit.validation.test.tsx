// 00-SPEC §2.1: client validation "mirrors server rules without replacing them".
// Proves the mirror is GENERATED from openapi.json, not hand-typed.
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import openapi from "../src/api/openapi.json";
import Submit from "../src/pages/Submit";
import { server } from "../mocks/node";
import { renderAt } from "./render";

it("blocks a 9-char complaint with the bound read from the generated schema", async () => {
  const minLength = openapi.components.schemas.ComplaintCreate.properties.text.minLength;
  let posted = false;
  server.use(http.post("/api/complaints", () => ((posted = true), HttpResponse.json({}, { status: 500 }))));
  const user = userEvent.setup();
  renderAt(<Submit />);

  await user.type(screen.getByLabelText(/what's the problem/i), "x".repeat(minLength - 1));
  await user.type(screen.getByLabelText(/where/i), "G-9/1, Islamabad");
  await user.click(screen.getByRole("button", { name: /submit report/i }));

  expect(await screen.findByText(`Must be at least ${minLength} characters.`)).toBeVisible();
  expect(screen.getByLabelText(/what's the problem/i)).toHaveAttribute("aria-invalid", "true");
  expect(posted).toBe(false);
});
