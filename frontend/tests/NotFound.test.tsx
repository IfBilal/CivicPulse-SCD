import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import NotFound from "../src/pages/NotFound";
import { renderAt } from "./render";

it("shows a 404 message and links back to the home route", async () => {
  renderAt(<NotFound />, "/anything-unmapped", "/anything-unmapped");

  expect(screen.getByText(/off the grid/i)).toBeInTheDocument();
  expect(screen.getByText(/404/i)).toBeInTheDocument();

  const link = screen.getByRole("link", { name: /report a problem/i });
  expect(link).toHaveAttribute("href", "/");

  const user = userEvent.setup();
  await user.click(link);
  expect(screen.getByTestId("location")).toHaveTextContent("/");
});
