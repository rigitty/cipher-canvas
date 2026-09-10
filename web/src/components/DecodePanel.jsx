import { useState } from "react";
import DropZone from "./DropZone.jsx";
import { decodeImage } from "../api.js";

export default function DecodePanel() {
  const [carrier, setCarrier] = useState(null);
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState(null);
  const [copied, setCopied] = useState(false);

  const canDecode = carrier && passphrase.length > 0;

  const submit = async () => {
    setBusy(true);
    setError("");
    setMessage(null);
    setCopied(false);
    try {
      const text = await decodeImage({ carrier, passphrase });
      setMessage(text);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(message);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="panel">
      <section className="panel-section">
        <h2 className="section-title">CARRIER IMAGE</h2>
        <DropZone file={carrier} onFile={(f) => { setCarrier(f); setError(""); setMessage(null); }} label="Select the encoded image" />
        {carrier && (
          <div className="file-meta">
            <span>{carrier.name}</span>
          </div>
        )}
      </section>

      <section className="panel-section">
        <h2 className="section-title">PASSPHRASE</h2>
        <input
          type="password"
          className="text-input single"
          placeholder="Passphrase used during encoding"
          value={passphrase}
          autoComplete="off"
          onChange={(e) => {
            setPassphrase(e.target.value);
            setError("");
          }}
        />
        <button
          type="button"
          className="action-btn"
          disabled={!canDecode || busy}
          onClick={submit}
        >
          {busy ? "DECODING..." : "DECODE IMAGE"}
        </button>
      </section>

      {error && <div className="error-box">{error}</div>}

      {message !== null && (
        <section className="panel-section result-box">
          <h2 className="section-title">EXTRACTED MESSAGE</h2>
          <div className="extracted-actions">
            <button type="button" className="ghost-btn" onClick={copy}>
              {copied ? "COPIED" : "COPY"}
            </button>
          </div>
          <pre className="message-output">{message}</pre>
        </section>
      )}
    </div>
  );
}
