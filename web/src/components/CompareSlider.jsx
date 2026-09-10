import { useRef, useState } from "react";

export default function CompareSlider({ leftUrl, rightUrl, leftLabel, rightLabel }) {
  const [pos, setPos] = useState(50);
  const containerRef = useRef(null);

  const setFromClientX = (clientX) => {
    const rect = containerRef.current.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setPos(Math.max(0, Math.min(100, pct)));
  };

  return (
    <div
      ref={containerRef}
      className="compare"
      onPointerDown={(e) => {
        e.currentTarget.setPointerCapture(e.pointerId);
        setFromClientX(e.clientX);
      }}
      onPointerMove={(e) => {
        if (e.buttons & 1) setFromClientX(e.clientX);
      }}
    >
      <img className="compare-img" src={rightUrl} alt={rightLabel} draggable={false} />
      <div className="compare-clip" style={{ width: `${pos}%` }}>
        <img
          className="compare-img"
          src={leftUrl}
          alt={leftLabel}
          draggable={false}
          style={{ width: `${100 / (pos / 100)}%` }}
        />
      </div>
      <div className="compare-handle" style={{ left: `${pos}%` }}>
        <span className="compare-grip" />
      </div>
      <span className="compare-tag left">{leftLabel}</span>
      <span className="compare-tag right">{rightLabel}</span>
    </div>
  );
}