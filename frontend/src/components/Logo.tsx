import { useId } from "react";

/**
 * GoPass mark (proposal D-38, pending the team's vote): a ticket with side notches and a four-point star, filled with
 * the primary-to-secondary gradient. Decorative: the wordmark next to it carries the name.
 */
export default function Logo({ size = 36 }: { size?: number }) {
  const gradientId = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--color-primary)" />
          <stop offset="100%" stopColor="var(--color-secondary)" />
        </linearGradient>
      </defs>
      <g transform="rotate(-12 24 24)">
        <path
          fill={`url(#${gradientId})`}
          d="M9 10H39A5 5 0 0 1 44 15V20A4 4 0 0 0 44 28V33A5 5 0 0 1 39 38H9A5 5 0 0 1 4 33V28A4 4 0 0 0 4 20V15A5 5 0 0 1 9 10Z"
        />
        <path
          fill="#ffffff"
          d="M24 15C25 21 27 23 33 24C27 25 25 27 24 33C23 27 21 25 15 24C21 23 23 21 24 15Z"
        />
      </g>
    </svg>
  );
}
