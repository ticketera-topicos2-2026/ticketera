import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Typography of the proposal D-38, served from the project (no external font CDN).
import "@fontsource/plus-jakarta-sans/600.css";
import "@fontsource/plus-jakarta-sans/700.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "./styles.css";

import App from "./App";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element in index.html");
}

// Public address of the gateway, set by Compose from GATEWAY_PORT (DS-15).
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
if (!apiBaseUrl) {
  throw new Error("Missing VITE_API_BASE_URL: the address of the gateway, for example http://localhost:18080");
}

createRoot(root).render(
  <StrictMode>
    <App apiBaseUrl={apiBaseUrl} />
  </StrictMode>,
);
