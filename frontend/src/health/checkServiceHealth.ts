/** Health check of one backend service through the gateway (spec platform/service-health; DS-15). */

/** The backend services the status page shows. */
export const BACKEND_SERVICES = ["catalog", "sales", "payments"] as const;

/** Time limit of each health request: one slow service does not delay the others (DS-15). */
export const HEALTH_TIMEOUT_MS = 5_000;

/** Why a service is unhealthy: a status code other than 200, no answer in time, or no HTTP response at all. */
export type HealthFailure = "status" | "timeout" | "network";

export interface HealthResult {
  service: string;
  healthy: boolean;
  failure?: HealthFailure;
}

export interface HealthCheckOptions {
  timeoutMs?: number;
  /** Aborts the request early, for example when the page stops caring about the answer. */
  cancel?: AbortSignal;
}

/**
 * Requests GET <apiBaseUrl>/api/<service>/health with its own AbortController, aborted after the time limit. The
 * service is healthy only when it answers 200. A failed fetch that was not aborted means no HTTP response arrived,
 * which is how an unreachable gateway shows up in the browser.
 */
export async function checkServiceHealth(
  apiBaseUrl: string,
  service: string,
  { timeoutMs = HEALTH_TIMEOUT_MS, cancel }: HealthCheckOptions = {},
): Promise<HealthResult> {
  const controller = new AbortController();
  const abort = () => {
    controller.abort();
  };
  const timer = setTimeout(abort, timeoutMs);
  cancel?.addEventListener("abort", abort, { once: true });
  try {
    const response = await fetch(`${apiBaseUrl.replace(/\/+$/, "")}/api/${service}/health`, {
      signal: controller.signal,
      // Accept is a CORS-safelisted header, so the browser sends no preflight.
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    return response.status === 200 ? { service, healthy: true } : { service, healthy: false, failure: "status" };
  } catch {
    return { service, healthy: false, failure: controller.signal.aborted ? "timeout" : "network" };
  } finally {
    clearTimeout(timer);
    cancel?.removeEventListener("abort", abort);
  }
}
