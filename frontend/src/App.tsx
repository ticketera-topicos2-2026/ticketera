import { useEffect, useState } from "react";

import Logo from "./components/Logo";
import { BACKEND_SERVICES, checkServiceHealth } from "./health/checkServiceHealth";

type Health = "checking" | "healthy" | "unhealthy";

const HEALTH_LABELS: Record<Health, string> = {
  checking: "Comprobando…",
  healthy: "Disponible",
  unhealthy: "No disponible",
};

const SERVICE_DESCRIPTIONS: Record<string, string> = {
  catalog: "Catálogo de eventos",
  sales: "Ventas y entradas",
  payments: "Pagos",
};

export interface AppProps {
  /** Public address of the gateway, for example http://localhost:18080 (VITE_API_BASE_URL). */
  apiBaseUrl: string;
  services?: readonly string[];
}

/**
 * Status page of the bootstrap (D-32; spec platform/service-health): the health of every backend service through
 * the gateway, each request with its own 5-second limit (DS-15). Base style of the GoPass identity (D-38).
 */
export default function App({ apiBaseUrl, services = BACKEND_SERVICES }: AppProps) {
  const [health, setHealth] = useState<Record<string, Health>>(() =>
    Object.fromEntries(services.map((service) => [service, "checking"])),
  );
  const [gatewayUnreachable, setGatewayUnreachable] = useState(false);

  useEffect(() => {
    const cancel = new AbortController();
    let active = true;
    const checks = services.map(async (service) => {
      const result = await checkServiceHealth(apiBaseUrl, service, { cancel: cancel.signal });
      // Each service is shown as soon as its own answer arrives.
      if (active) {
        setHealth((current) => ({ ...current, [service]: result.healthy ? "healthy" : "unhealthy" }));
      }
      return result;
    });
    void Promise.all(checks).then((results) => {
      // No HTTP response at all from any service: the gateway itself cannot be reached.
      if (active) {
        setGatewayUnreachable(results.length > 0 && results.every((result) => result.failure === "network"));
      }
    });
    return () => {
      active = false;
      cancel.abort();
    };
  }, [apiBaseUrl, services]);

  return (
    <div className="page">
      <header className="topbar">
        <Logo />
        <span className="wordmark">
          Go<span className="wordmark__accent">Pass</span>
        </span>
      </header>

      <main className="content">
        <section className="hero">
          <p className="eyebrow">Plataforma</p>
          <h1>Estado del sistema</h1>
          <p className="lead">
            Salud de cada servicio, consultada a través del gateway en <code>{apiBaseUrl}</code>.
          </p>
        </section>

        {gatewayUnreachable && (
          <div role="alert" className="alert">
            <strong>No se puede conectar con el gateway</strong> en <code>{apiBaseUrl}</code>. Revisá que el sistema
            esté levantado con <code>docker compose up</code>.
          </div>
        )}

        <ul className="services" aria-label="Servicios">
          {services.map((service) => {
            const state = health[service] ?? "checking";
            return (
              <li
                key={service}
                className="service-card"
                aria-labelledby={`service-${service}`}
                data-health={state}
              >
                <div>
                  <h2 id={`service-${service}`}>{service}</h2>
                  <p className="service-card__description">{SERVICE_DESCRIPTIONS[service] ?? "Servicio"}</p>
                </div>
                <p className={`badge badge--${state}`}>
                  <span className="badge__dot" aria-hidden="true" />
                  {HEALTH_LABELS[state]}
                </p>
              </li>
            );
          })}
        </ul>
      </main>

      <footer className="footer">Viví tus eventos. Conseguí tus entradas.</footer>
    </div>
  );
}
