import "@fontsource-variable/space-grotesk";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "./styles/global.css";
import "./styles/pages.css";
import "./styles/story.css";

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

function mount(): void {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </BrowserRouter>
    </StrictMode>,
  );
}

// Never let the mock layer block the app: if MSW fails to start, render anyway and say why.
enableMocks()
  .catch((e: unknown) => console.error("[civicpulse] MSW failed to start — API calls will hit the network", e))
  .finally(mount);
