// 00-SPEC §2.1: "Render the loading state honestly — AI calls take seconds."
import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http } from "msw";

import Submit from "../src/pages/Submit";
import { CLASSIFYING_AFTER_MS, SLOW_AFTER_MS } from "../src/pages/submitForm";
import { server } from "../mocks/node";
import { renderAt } from "./render";

afterEach(() => vi.useRealTimers());

it("escalates the loading copy at 1.5 s and 6 s instead of a bare spinner", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  server.use(http.post("/api/complaints", async () => (await delay("infinite"), new Response())));
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  renderAt(<Submit />);
  await user.type(screen.getByLabelText(/what's the problem/i), "Nala block hai, pani ghar mein");
  await user.type(screen.getByLabelText(/where/i), "Dhok Hassu");
  await user.click(screen.getByRole("button", { name: /submit report/i }));

  expect(screen.getByRole("status")).toHaveTextContent("Sending your report…");
  await act(() => vi.advanceTimersByTimeAsync(CLASSIFYING_AFTER_MS + 100));
  expect(screen.getByRole("status")).toHaveTextContent("Classifying with AI…");
  await act(() => vi.advanceTimersByTimeAsync(SLOW_AFTER_MS - CLASSIFYING_AFTER_MS));
  expect(screen.getByRole("status")).toHaveTextContent("The model is slow — we'll fall back to keyword rules if needed.");
  expect(screen.getByRole("button", { name: /working/i })).toBeDisabled();
});
