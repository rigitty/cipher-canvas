import { useRef, useState } from "react";
import DropZone from "./DropZone.jsx";
import EntropyMeter from "./EntropyMeter.jsx";
import ProgressBar from "./ProgressBar.jsx";
import ShardPanel from "./ShardPanel.jsx";
import { decodeImage, isTauri, saveFileNative } from "../api.js";

export default function DecodePanel() {
  const [carrierType, setCarrierType] = useState("single"); // "single" | "multi"
  const [carrier, setCarrier] = useState(null);
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveNote, setSaveNote] = useState("");
  const [saveName, setSaveName] = useState("");
  const downloadRef = useRef(null);

  const canDecode = carrier && passphrase.length > 0;
  const isImage = result !== null && result.type.startsWith("image/");

  const decodeStages = [
    { at: 20, text: "Reading carrier image..." },
    { at: 50, text: "Scanning stealth bits & DCT blocks..." },
    { at: 75, text: "Decrypting payload with passphrase..." },
    { at: 92, text: "Extracting secret message / file..." },
  ];

  const submit = async () => {
    setBusy(true);
    setError("");
    setResult(null);
    setCopied(false);
    setSaveNote("");
    try {
      const decoded = await decodeImage({ carrier, passphrase });
      setResult(decoded);
      setSaveName(decoded.filename);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(result.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const save = async () => {
    setSaving(true);
    setSaveNote("");
    try {
      const ext = saveName.includes(".") ? saveName.split(".").pop() : "";
      if (isTauri()) {
        const path = await saveFileNative(saveName, result.blob, null, null);
        setSaveNote(`saved to ${path}`);
      } else {
        const anchor = document.createElement("a");
        anchor.href = result.url;
        anchor.download = saveName;
        anchor.click();
      }
      void ext;
    } catch (err) {
      setSaveNote(String(err).includes("cancelled") ? "save cancelled" : `save failed: ${err}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel">
      <div className="segmented shard-nav-tabs" style={{ marginBottom: "16px" }}>
        <button
          type="button"
          className={carrierType === "single" ? "active" : ""}
          onClick={() => setCarrierType("single")}
        >
          SINGLE CARRIER
        </button>
        <button
          type="button"
          className={carrierType === "multi" ? "active" : ""}
          onClick={() => setCarrierType("multi")}
        >
          MULTI-IMAGE ASSEMBLE
        </button>
      </div>

      {carrierType === "multi" ? (
        <ShardPanel defaultSubTab="decode" />
      ) : (
        <>
          <div className="panel-grid">
            <section className="panel-section">
              <h2 className="section-title">CARRIER IMAGE</h2>
          <DropZone
            file={carrier}
            onFile={(f) => {
              setCarrier(f);
              setError("");
              setResult(null);
            }}
            label="Select the encoded image"
          />
          {carrier && (
            <div className="file-meta">
              <span>{carrier.name}</span>
            </div>
          )}
        </section>

        <section className="panel-section">
          <h2 className="section-title">PASSPHRASE &amp; DECRYPTION</h2>
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
          <EntropyMeter passphrase={passphrase} />
          <button
            type="button"
            className="action-btn"
            disabled={!canDecode || busy}
            onClick={submit}
          >
            {busy ? "DECODING CARRIER..." : "DECODE CARRIER"}
          </button>
          <ProgressBar busy={busy} stages={decodeStages} />
          <div className="robust-tip-box" style={{ marginTop: "8px" }}>
            Auto-detects both <b>Stealth</b> and <b>Robust</b> carriers.
          </div>
        </section>
      </div>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <section className="panel-section result-box">
          <h2 className="section-title">EXTRACTED FILE</h2>
          <div className="file-meta">
            <span>{result.filename}</span>
            <span>{result.size} bytes</span>
            <span>{result.type}</span>
          </div>

          {isImage && (
            <img className="result-preview wide" src={result.url} alt="extracted image" />
          )}

          {result.text !== null ? (
            <>
              <div className="extracted-actions">
                <button type="button" className="ghost-btn" onClick={copy}>
                  {copied ? "COPIED" : "COPY"}
                </button>
              </div>
              <pre className="message-output">{result.text}</pre>
            </>
          ) : (
            <p className="result-note">
              Binary file — save it to disk to open it.
            </p>
          )}

          <input
            type="text"
            className="text-input single"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
          />
          {isTauri() ? (
            <button
              type="button"
              className="action-btn"
              onClick={save}
              disabled={saving}
            >
              {saving ? "SAVING..." : "SAVE FILE"}
            </button>
          ) : (
            <a
              ref={downloadRef}
              className="action-btn"
              href={result.url}
              download={saveName}
            >
              SAVE FILE
            </a>
          )}
          {saveNote && <div className="hint-box">{saveNote}</div>}
        </section>
      )}
      </>
      )}
    </div>
  );
}