import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { fake } from "../mocks/handlers";
import { server } from "../mocks/node";

// MSW intercepts at the network layer: components use the REAL client and REAL types.
// onUnhandledRequest "error" is the "zero real network" guarantee for the test suite.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  fake.reset();
});
afterAll(() => server.close());
