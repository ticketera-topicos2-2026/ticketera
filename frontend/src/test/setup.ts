import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Adds the DOM matchers of jest-dom (toBeInTheDocument, toHaveAttribute...) to Vitest's expect.
import "@testing-library/jest-dom/vitest";

// Vitest runs without globals, so Testing Library cannot register its own cleanup.
afterEach(() => {
  cleanup();
});
