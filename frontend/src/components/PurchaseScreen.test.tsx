import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PurchaseScreen } from "./PurchaseScreen";

describe("PurchaseScreen", () => {
  const seatsMock = [
    { seat_id: "A-1", category: "VIP", price_centavos: 1500000, status: "AVAILABLE" },
    { seat_id: "A-2", category: "GENERAL", price_centavos: 750000, status: "AVAILABLE" },
    { seat_id: "A-3", category: "GENERAL", price_centavos: 750000, status: "SOLD" },
  ];

  it("renders seat list and calculates total when selecting seats", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => seatsMock,
    }));

    render(<PurchaseScreen eventId="ev-1" onPurchaseSuccess={vi.fn()} />);

    expect(await screen.findByText(/A-1/)).toBeInTheDocument();
    expect(screen.getByText(/A-2/)).toBeInTheDocument();
    expect(screen.getByText(/A-3/)).toBeInTheDocument();

    // Select seat A-1
    const seatA1 = screen.getByRole("button", { name: /A-1/ });
    fireEvent.click(seatA1);

    expect(screen.getByText(/Total: \$ 15.000,00/i)).toBeInTheDocument();

    // Select seat A-2
    const seatA2 = screen.getByRole("button", { name: /A-2/ });
    fireEvent.click(seatA2);

    expect(screen.getByText(/Total: \$ 22.500,00/i)).toBeInTheDocument();
  });

  it("submits purchase with Idempotency-Key header", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => seatsMock,
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          order_id: "ord-123",
          event_id: "ev-1",
          customer_id: "cust-1",
          total_amount_centavos: 1500000,
          currency: "ARS",
          status: "CONFIRMED",
          tickets: [{ ticket_id: "tkt-1", seat_id: "A-1", code: "TCK-A-1-XYZ" }],
        }),
      });

    vi.stubGlobal("fetch", fetchMock);
    const onSuccess = vi.fn();

    render(<PurchaseScreen eventId="ev-1" onPurchaseSuccess={onSuccess} />);

    const seatA1 = await screen.findByRole("button", { name: /A-1/ });
    fireEvent.click(seatA1);

    const buyBtn = screen.getByRole("button", { name: /Confirmar Compra/i });
    fireEvent.click(buyBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/sales/events/ev-1/orders",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "Idempotency-Key": expect.any(String),
          }),
        })
      );
      expect(onSuccess).toHaveBeenCalledWith("ord-123");
    });
  });
});
