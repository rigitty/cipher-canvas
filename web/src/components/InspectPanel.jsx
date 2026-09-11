import { useState } from "react";
import DropZone from "./DropZone.jsx";
import ProgressBar from "./ProgressBar.jsx";
import { inspectImage } from "../api.js";

export default function InspectPanel() {
  const [image, setImage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [activeView, setActiveView] = useState("lsb"); // "lsb" or "original"

  const inspectStages = [
    { at: 20, text: "Reading image bit planes..." },
    { at: 50, text: "Computing Chi-Square distribution..." },
    { at: 80, text: "Analyzing pixel pair anomalies..." },
    { at: 92, text: "Generating forensic report..." },
  ];

  const runInspect = async (fileToInspect) => {
    const target = fileToInspect || image;
    if (!target) return;

    setBusy(true);
    setError("");
    setResult(null);

    try {
      const data = await inspectImage(target);
      setResult(data);
    } catch (err) {
      setError(err.message || "Steganalysis inspection failed");
    } finally {
      setBusy(false);
    }
  };

  const handleFile = (f) => {
    setImage(f);
    setError("");
    setResult(null);
    runInspect(f);
  };

  return (
    <div className="panel">
      <div className="panel-grid">
        <section className="panel-section">
          <h2 className="section-title">CARRIER FORENSIC INSPECTION</h2>
          <DropZone
            file={image}
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
              <ProgressBar busy={busy} stages={inspectStages} />
            </div>
          )}

          {error && <div className="error-banner">{error}</div>}
        </section>

        {result && (
          <section className="panel-section inspect-results-section">
            <h2 className="section-title">STEGANALYSIS VERDICT</h2>

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
                    <small>ANOMALY</small>
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
                  <span className="stat-title">RED CHANNEL</span>
                  <span className="stat-val">{result.chi_square_per_df.red}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-title">GREEN CHANNEL</span>
                  <span className="stat-val">{result.chi_square_per_df.green}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-title">BLUE CHANNEL</span>
                  <span className="stat-val">{result.chi_square_per_df.blue}</span>
                </div>
                <div className="stat-card">
                  <span className="stat-title">AVERAGE</span>
                  <span className="stat-val highlight">{result.chi_square_per_df.average}</span>
                </div>
              </div>
            </div>
          </section>
        )}
      </div>

      {result && (
        <>
          <section className="panel-section">
            <div className="section-header-row">
              <h2 className="section-title">BIT PLANE VISUALIZER (LSB PLANE)</h2>
              <div className="toggle-group">
                <button
                  type="button"
                  className={`toggle-btn ${activeView === "lsb" ? "active" : ""}`}
                  onClick={() => setActiveView("lsb")}
                >
                  LSB BIT PLANE
                </button>
                <button
                  type="button"
                  className={`toggle-btn ${activeView === "original" ? "active" : ""}`}
                  onClick={() => setActiveView("original")}
                >
                  ORIGINAL VIEW
                </button>
              </div>
            </div>

            <div className="bit-plane-viewer-wrap">
              {activeView === "lsb" ? (
                <div className="bit-plane-display">
                  <img
                    src={result.lsb_preview}
                    alt="LSB Bit Plane Visualization"
                    className="bit-plane-img"
                  />
                  <div className="bit-plane-legend">
                    <span>LSB bit plane map — reveals hidden patterns if unscattered</span>
                    <a
                      href={result.lsb_preview}
                      download="lsb-bit-plane.png"
                      className="download-link"
                    >
                      Export Map
                    </a>
                  </div>
                </div>
              ) : (
                <div className="bit-plane-display">
                  <img
                    src={URL.createObjectURL(image)}
                    alt="Original Carrier View"
                    className="bit-plane-img"
                  />
                </div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
