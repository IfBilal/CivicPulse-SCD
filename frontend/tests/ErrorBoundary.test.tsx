// 11-FRONTEND §3.4: a render-time crash shows the fallback with the LAST X-Request-ID seen.
import { render, screen } from "@testing-library/react";

import { api } from "../src/api/client";
import { ErrorBoundary } from "../src/components/ErrorBoundary";

function Boom(): never {
  throw new Error("render exploded");
}

it("shows the last request id the client saw when a child throws during render", async () => {
  await api.getComplaint("00000000-4c1a-4b0e-9d2f-000000000001");
  const spy = vi.spyOn(console, "error").mockImplementation(() => {});
  render(
    <ErrorBoundary>
      <Boom />
    </ErrorBoundary>,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("Something broke on this screen.");
  expect(screen.getByTestId("last-request-id").textContent).toMatch(/^[0-9a-f-]{36}$/);
  spy.mockRestore();
});
