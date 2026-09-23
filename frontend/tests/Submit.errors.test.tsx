// grilled-meat finding: a 400 whose field isn't an input (e.g. malformed body) must still surface.
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import Submit from "../src/pages/Submit";
import { server } from "../mocks/node";
import { renderAt } from "./render";

it("shows the envelope message when the server reports a non-input field", async () => {
  server.use(
    http.post("/api/complaints", () =>
      HttpResponse.json(
        { error: { code: "validation_error", message: "Request body failed validation.", request_id: "r", fields: [{ field: "body", code: "invalid_json", message: "Invalid JSON" }] } },
        { status: 400 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderAt(<Submit />);
  await user.type(screen.getByLabelText(/what's the problem/i), "Kachra teen din se nahi uthaya");
  await user.type(screen.getByLabelText(/where/i), "I-8/2");
  await user.click(screen.getByRole("button", { name: /submit report/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Request body failed validation.");
});
