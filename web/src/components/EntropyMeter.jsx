import { useMemo } from "react";

export function calculateEntropy(passphrase) {
  if (!passphrase) return { bits: 0, level: 0, label: "empty", color: "var(--muted)" };

  let pool = 0;
  if (/[a-z]/.test(passphrase)) pool += 26;
  if (/[A-Z]/.test(passphrase)) pool += 26;
  if (/[0-9]/.test(passphrase)) pool += 10;
  if (/[^a-zA-Z0-9]/.test(passphrase)) pool += 32;

  const length = passphrase.length;
  // Account for repeated characters slightly discounting pure random entropy
  const uniqueChars = new Set(passphrase).size;
  const repetitionFactor = Math.min(1, uniqueChars / Math.max(1, length * 0.7));
  const bits = Math.round(length * Math.log2(Math.max(2, pool)) * repetitionFactor);

  if (bits < 28) {
    return { bits, level: 1, label: "Very Weak", color: "#e50914" };
  } else if (bits < 48) {
    return { bits, level: 2, label: "Weak", color: "#e67e22" };
  } else if (bits < 68) {
    return { bits, level: 3, label: "Good", color: "#f1c40f" };
  } else if (bits < 88) {
    return { bits, level: 4, label: "Strong", color: "#2ecc71" };
  } else {
    return { bits, level: 5, label: "Military-Grade", color: "#00ffaa" };
  }
}

export default function EntropyMeter({ passphrase }) {
  const { bits, level, label, color } = useMemo(
    () => calculateEntropy(passphrase),
    [passphrase]
  );

  if (!passphrase) return null;

  return (
    <div className="entropy-meter" title={`Entropy: ~${bits} bits (AES-256-GCM brute-force resistance)`}>
      <div className="entropy-bars">
        {[1, 2, 3, 4, 5].map((idx) => (
          <div
            key={idx}
            className="entropy-bar-segment"
            style={{
              backgroundColor: idx <= level ? color : "var(--border)",
              boxShadow: idx <= level ? `0 0 6px ${color}40` : "none",
            }}
          />
        ))}
      </div>
      <div className="entropy-info">
        <span className="entropy-label" style={{ color }}>
          {label}
        </span>
        <span className="entropy-bits">~{bits} bits entropy</span>
      </div>
    </div>
  );
}
