import "@fontsource-variable/space-grotesk";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "./styles/global.css";
import "./styles/pages.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";

async function enableMocks(): Promise<void> {
  // `npm run dev` runs in mode "mock": every /api call is answered by MSW in a service worker,
  // so the whole UI works with zero backend and zero real network. Never active in a prod build.
  if (import.meta.env.MODE !== "mock") return;
  const { worker } = await import("../mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass", quiet: true });
}

void enableMocks().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>,
  );
});
