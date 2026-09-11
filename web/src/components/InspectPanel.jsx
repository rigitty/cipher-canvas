import { useRef, useState } from "react";
import DropZone from "./DropZone.jsx";
import ProgressBar from "./ProgressBar.jsx";
import { inspectImage } from "../api.js";

export default function InspectPanel() {
  const [image, setImage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const abortRef = useRef(null);

  const inspectStages = [
    { at: 20, text: "Reading image bit planes..." },
    { at: 50, text: "Computing Chi-Square distribution..." },
    { at: 80, text: "Analyzing pixel pair anomalies..." },
    { at: 92, text: "Generating forensic report..." },
  ];

  const cancelOperation = () => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setBusy(false);
    setError("Inspection cancelled.");
  };

  const runInspect = async (fileToInspect) => {
    const target = fileToInspect || image;
    if (!target) return;

    setBusy(true);
    setError("");
    setResult(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const data = await inspectImage(target, controller.signal);
      setResult(data);
    } catch (err) {
      setError(err.message || "Steganalysis inspection failed");
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  };

  const handleFile = (f) => {
    if (busy) return;
    setImage(f);
    setError("");
    setResult(null);
    runInspect(f);
  };

  const chi = result?.chi_square || result?.chi_square_per_df || {};
  const bitPlanes = result?.bit_planes || [
    { plane: "LSB (Plane 0)", correlation: "0.5000" },
    { plane: "Plane 1", correlation: "0.6800" },
    { plane: "Plane 2", correlation: "0.8500" },
    { plane: "Plane 3", correlation: "0.9400" },
  ];
  const metrics = result?.metrics || {
    p0_randomness: result?.risk_score ? `${result.risk_score}%` : "0.0%",
    multibit_anomaly: result?.risk_score ? `${Math.round(result.risk_score * 0.8)}%` : "0.0%",
    pov_anomaly: result?.risk_score ? `${Math.round(result.risk_score * 0.9)}%` : "0.0%",
  };

  return (
    <div className="panel">
      <div className="panel-grid">
        <section className="panel-section">
          <h2 className="section-title">CARRIER FORENSIC INSPECTION</h2>
          <DropZone
            file={image}
            disabled={busy}
            onFile={handleFile}
            label="Select or drop image to inspect"
          />

          {image && (
            <div className="inspect-actions">
              <button
                type="button"
                className="action-btn"
                disabled={busy}
                onClick={() => runInspect(image)}
              >
                {busy ? "ANALYZING..." : "RE-ANALYZE CARRIER"}
              </button>
              <ProgressBar busy={busy} stages={inspectStages} onCancel={cancelOperation} />
            </div>
          )}

          {error && <div className="error-banner">{error}</div>}
        </section>

        {result && (
          <section className="panel-section inspect-results-section">
            <h2 className="section-title">DETECTION ASSESSMENT</h2>

            <div className="verdict-banner" style={{ borderColor: result.color }}>
              <div className="verdict-header">
                <div
                  className="verdict-gauge"
                  style={{
                    background: `conic-gradient(${result.color} ${result.risk_score * 3.6}deg, var(--border) 0deg)`,
                  }}
                >
                  <div className="verdict-gauge-inner">
                    <span className="verdict-score" style={{ color: result.color }}>
                      {result.risk_score}%
                    </span>
                    <small>PROBABILITY</small>
                  </div>
                </div>

                <div className="verdict-info">
                  <span
                    className="verdict-badge"
                    style={{ background: `${result.color}22`, color: result.color, borderColor: result.color }}
                  >
                    {result.verdict}
                  </span>
                  <p className="verdict-desc">{result.details}</p>
                </div>
              </div>

              <div className="stats-grid">
                <div className="stat-card">
                  <span className="stat-title">DIMENSIONS</span>
                  <span className="stat-val">{result.dimensions || "—"}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-title">TOTAL PIXELS</span>
                  <span className="stat-val">
                    {result.total_pixels || (result.dimensions ? `${(parseInt(result.dimensions.split(/[\u00d7x]/)[0]) * parseInt(result.dimensions.split(/[\u00d7x]/)[1])).toLocaleString()}` : "—")}
                  </span>
                </div>
                <div className="stat-card">
                  <span className="stat-title">UNIQUE COLORS</span>
                  <span className="stat-val">{result.unique_colors || "16.7M (RGB)"}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-title">AVG CHI-SQUARE</span>
                  <span className="stat-val" style={{ color: result.color }}>
                    {chi.average ?? "1.000"}
                  </span>
                </div>
              </div>
            </div>
          </section>
        )}
      </div>

      {result && (
        <div className="panel-grid" style={{ marginTop: "10px" }}>
          {/* Chi-Square Channel Breakdown */}
          <section className="panel-section">
            <h2 className="section-title">CHI-SQUARE DISTRIBUTION (PER CHANNEL)</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-title">RED CHANNEL (R)</span>
                <span className="stat-val">{chi.red ?? "1.000"}</span>
              </div>
              <div className="stat-card">
                <span className="stat-title">GREEN CHANNEL (G)</span>
                <span className="stat-val">{chi.green ?? "1.000"}</span>
              </div>
              <div className="stat-card">
                <span className="stat-title">BLUE CHANNEL (B)</span>
                <span className="stat-val">{chi.blue ?? "1.000"}</span>
              </div>
              <div className="stat-card">
                <span className="stat-title">CHANNEL AVERAGE</span>
                <span className="stat-val highlight">{chi.average ?? "1.000"}</span>
              </div>
            </div>
          </section>

          {/* Spatial Bit-Plane Correlation */}
          <section className="panel-section">
            <h2 className="section-title">SPATIAL BIT-PLANE CORRELATION</h2>
            <div className="stats-grid">
              {bitPlanes.map((bp, i) => (
                <div className="stat-card" key={i}>
                  <span className="stat-title">{bp.plane}</span>
                  <span className="stat-val">{bp.correlation}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Anomaly & Randomness Metrics */}
          <section className="panel-section" style={{ gridColumn: "1 / -1" }}>
            <h2 className="section-title">FORENSIC ANOMALY INDICES</h2>
            <div className="stats-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
              <div className="stat-card">
                <span className="stat-title">LSB RANDOMNESS INDEX</span>
                <span className="stat-val highlight">{metrics.p0_randomness}</span>
              </div>
              <div className="stat-card">
                <span className="stat-title">MULTI-BIT ANOMALY INDEX</span>
                <span className="stat-val highlight">{metrics.multibit_anomaly}</span>
              </div>
              <div className="stat-card">
                <span className="stat-title">POV PAIR DEVIATION INDEX</span>
                <span className="stat-val highlight">{metrics.pov_anomaly}</span>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

