import React, { useEffect, useState } from "react";

interface Seat {
  seat_id: string;
  category: string;
  price_centavos: number;
  status: "AVAILABLE" | "SOLD";
}

interface PurchaseScreenProps {
  eventId: string;
  onPurchaseSuccess: (orderId: string) => void;
}

export const PurchaseScreen: React.FC<PurchaseScreenProps> = ({
  eventId,
  onPurchaseSuccess,
}) => {
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selectedSeatIds, setSelectedSeatIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/sales/events/${eventId}/seats?status=AVAILABLE`)
      .then((res) => res.json())
      .then((data) => setSeats(data))
      .catch((err) => setError(err.message));
  }, [eventId]);

  const toggleSeat = (seatId: string) => {
    setSelectedSeatIds((prev) =>
      prev.includes(seatId)
        ? prev.filter((id) => id !== seatId)
        : [...prev, seatId]
    );
  };

  const selectedSeats = seats.filter((s) => selectedSeatIds.includes(s.seat_id));
  const totalCentavos = selectedSeats.reduce((acc, s) => acc + s.price_centavos, 0);

  const formatPrice = (centavos: number) => {
    const formatted = (centavos / 100).toLocaleString("es-AR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `$ ${formatted}`;
  };

  const handlePurchase = async () => {
    if (selectedSeatIds.length === 0) return;
    setLoading(true);
    setError(null);

    const idempotencyKey = crypto.randomUUID();

    try {
      const response = await fetch(`/api/sales/events/${eventId}/orders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ seat_ids: selectedSeatIds }),
      });

      if (!response.ok) {
        throw new Error(`Error en la compra: HTTP ${response.status}`);
      }

      const order = await response.json();
      onPurchaseSuccess(order.order_id);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Error desconocido al procesar la compra");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Selección de Asientos</h2>

      {error && <div className="p-4 bg-red-100 text-red-700 rounded-md">{error}</div>}

      <div className="grid grid-cols-4 gap-4">
        {seats.map((seat) => {
          const isSelected = selectedSeatIds.includes(seat.seat_id);
          const isSold = seat.status === "SOLD";

          return (
            <button
              key={seat.seat_id}
              disabled={isSold}
              onClick={() => toggleSeat(seat.seat_id)}
              className={`p-4 border rounded-lg text-center transition-colors ${
                isSold
                  ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                  : isSelected
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-800 hover:bg-gray-50 border-gray-300"
              }`}
            >
              <div className="font-bold">{seat.seat_id}</div>
              <div className="text-xs">{seat.category}</div>
              <div className="text-sm font-semibold mt-1">
                {isSold ? "OCUPADO" : formatPrice(seat.price_centavos)}
              </div>
            </button>
          );
        })}
      </div>

      <div className="border-t pt-4 flex items-center justify-between">
        <div>
          <div className="text-sm text-gray-500">
            {selectedSeatIds.length} asiento(s) seleccionado(s)
          </div>
          <div className="text-xl font-bold text-gray-900">
            Total: {formatPrice(totalCentavos)}
          </div>
        </div>

        <button
          onClick={handlePurchase}
          disabled={selectedSeatIds.length === 0 || loading}
          className="px-6 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Procesando..." : "Confirmar Compra"}
        </button>
      </div>
    </div>
  );
};
