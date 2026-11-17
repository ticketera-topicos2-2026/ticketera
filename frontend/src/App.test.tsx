/**
 * Tests of the status page (spec platform/service-health; DS-15). Every request goes through a stubbed fetch that
 * answers like the gateway: a status code per service, a network error when the gateway is down, or no answer at
 * all until the request is aborted.
 */
import { act, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const API_BASE_URL = "http://gateway.test:18080";
const SERVICES = ["catalog", "sales", "payments"] as const;

type Service = (typeof SERVICES)[number];
type Behavior = number | "network-error" | "no-answer";

/** Replaces fetch with the gateway behavior of each service and returns the mock. */
function stubGateway(behaviors: Record<Service, Behavior>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const path = new URL(String(input)).pathname;
    const service = /^\/api\/([^/]+)\/health$/.exec(path)?.[1] as Service | undefined;
    const behavior: Behavior = service ? behaviors[service] : 404;
    if (behavior === "network-error") {
      return Promise.reject(new TypeError("Failed to fetch"));
    }
    if (behavior === "no-answer") {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        });
      });
    }
    return Promise.resolve(new Response(null, { status: behavior }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The list item of a service, found by its accessible name. */
function serviceItem(service: Service) {
  return screen.getByRole("listitem", { name: service });
}

function expectHealth(service: Service, label: "Disponible" | "No disponible" | "Comprobando…") {
  expect(within(serviceItem(service)).getByText(label)).toBeInTheDocument();
}

/** Runs pending timers and promise callbacks up to the given time, inside act. */
async function advance(milliseconds: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(milliseconds);
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("status page", () => {
  it("shows catalog, sales and payments as healthy when every service answers 200", async () => {
    // Req: The status page shows the health of every backend service. Scenario: All services healthy.
    vi.useFakeTimers();
    stubGateway({ catalog: 200, sales: 200, payments: 200 });

    render(<App apiBaseUrl={API_BASE_URL} />);
    await advance(0);

    for (const service of SERVICES) {
      expectHealth(service, "Disponible");
    }
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("requests the health of each service through the gateway, each with its own AbortController", async () => {
    // DS-15: one AbortController per request, so one slow service does not delay the others.
    vi.useFakeTimers();
    const fetchMock = stubGateway({ catalog: 200, sales: 200, payments: 200 });

    render(<App apiBaseUrl={API_BASE_URL} />);
    await advance(0);

    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    for (const service of SERVICES) {
      expect(urls).toContain(`${API_BASE_URL}/api/${service}/health`);
    }
    const signals = fetchMock.mock.calls.map(([, init]) => init?.signal);
    expect(signals.every((signal) => signal instanceof AbortSignal)).toBe(true);
    expect(new Set(signals).size).toBe(signals.length);
  });

  it("shows sales as unhealthy when it answers 503 and the others as healthy", async () => {
    // Req: The status page shows the health of every backend service. Scenario: One service unhealthy.
    vi.useFakeTimers();
    stubGateway({ catalog: 200, sales: 503, payments: 200 });

    render(<App apiBaseUrl={API_BASE_URL} />);
    await advance(0);

    expectHealth("sales", "No disponible");
    expectHealth("catalog", "Disponible");
    expectHealth("payments", "Disponible");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows payments as unhealthy when the gateway answers 502 for it and the others as healthy", async () => {
    // Req: The status page shows the health of every backend service. Scenario: One service stopped.
    vi.useFakeTimers();
    stubGateway({ catalog: 200, sales: 200, payments: 502 });

    render(<App apiBaseUrl={API_BASE_URL} />);
    await advance(0);

    expectHealth("payments", "No disponible");
    expectHealth("catalog", "Disponible");
    expectHealth("sales", "Disponible");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a service that does not answer as unhealthy after 5 seconds, without delaying the others", async () => {
    // Req: Each health request of the status page has a time limit (5 seconds, DS-15).
    vi.useFakeTimers();
    stubGateway({ catalog: 200, sales: "no-answer", payments: 200 });

    render(<App apiBaseUrl={API_BASE_URL} />);
    await advance(0);

    expectHealth("catalog", "Disponible");
    expectHealth("payments", "Disponible");
    expectHealth("sales", "Comprobando…");

    await advance(4_999);
    expectHealth("sales", "Comprobando…");

    await advance(1);
    expectHealth("sales", "No disponible");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows every service as unhealthy and a message when the gateway cannot be reached", async () => {
    // Req: The status page shows an unreachable gateway. Scenario: Gateway stopped.
    vi.useFakeTimers();
    stubGateway({ catalog: "network-error", sales: "network-error", payments: "network-error" });

    render(<App apiBaseUrl={API_BASE_URL} />);
    await advance(0);

    for (const service of SERVICES) {
      expectHealth(service, "No disponible");
    }
    expect(screen.getByRole("alert")).toHaveTextContent(/no se puede conectar con el gateway/i);
  });

  it("does not report the gateway as unreachable when only one request fails at the network level", async () => {
    // Req: The status page shows an unreachable gateway: the message is for the gateway, not for one service.
    vi.useFakeTimers();
    stubGateway({ catalog: 200, sales: 200, payments: "network-error" });

    render(<App apiBaseUrl={API_BASE_URL} />);
    await advance(0);

    expectHealth("payments", "No disponible");
    expectHealth("catalog", "Disponible");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
