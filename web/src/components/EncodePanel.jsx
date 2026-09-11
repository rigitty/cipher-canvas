import { useEffect, useMemo, useRef, useState } from "react";
import DropZone from "./DropZone.jsx";
import CompareSlider from "./CompareSlider.jsx";
import EntropyMeter from "./EntropyMeter.jsx";
import ProgressBar from "./ProgressBar.jsx";
import ShardPanel from "./ShardPanel.jsx";
import {
  capacityBytes,
  capacityRobustBytes,
  encodeImage,
  isTauri,
  saveFileNative,
} from "../api.js";
import { buildDiffCanvas, objectUrlFor } from "../imageDiff.js";

async function readImageSize(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("cannot read image dimensions"));
    };
    img.src = url;
  });
}

export default function EncodePanel() {
  const [carrierType, setCarrierType] = useState("single"); // "single" | "multi"
  const [carrier, setCarrier] = useState(null);
  const [originalUrl, setOriginalUrl] = useState(null);
  const [carrierMeta, setCarrierMeta] = useState(null);
  const [mode, setMode] = useState("stealth"); // "stealth" | "robust"
  const [source, setSource] = useState("text");
  const [message, setMessage] = useState("");
  const [messageFile, setMessageFile] = useState(null);
  const [passphrase, setPassphrase] = useState("");
  const [bitDepth, setBitDepth] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [savedName, setSavedName] = useState("carrier.png");
  const [showDiff, setShowDiff] = useState(false);
  const [diff, setDiff] = useState(null);
  const [diffBusy, setDiffBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveNote, setSaveNote] = useState("");
  const downloadRef = useRef(null);

  const filenameLength =
    source === "file" && messageFile
      ? new TextEncoder().encode(messageFile.name).length
      : new TextEncoder().encode("message.txt").length;

  const capacity = useMemo(() => {
    if (!carrierMeta) return null;
    if (mode === "robust") {
      return capacityRobustBytes(carrierMeta.width, carrierMeta.height);
    }
    return capacityBytes(
      carrierMeta.width,
      carrierMeta.height,
      filenameLength,
      bitDepth
    );
  }, [carrierMeta, filenameLength, bitDepth, mode]);

  useEffect(() => () => {
    if (originalUrl) URL.revokeObjectURL(originalUrl);
  }, [originalUrl]);

  const onCarrier = async (file) => {
    try {
      const meta = await readImageSize(file);
      if (originalUrl) URL.revokeObjectURL(originalUrl);
      setCarrier(file);
      setOriginalUrl(await objectUrlFor(file));
      setCarrierMeta(meta);
      setResult(null);
      setDiff(null);
      setShowDiff(false);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  };

  const messageBytes =
    source === "file" && messageFile
      ? messageFile.size
      : new Blob([message]).size;

  const overCapacity = capacity !== null && messageBytes > capacity;
  const disabledHint = !carrier
    ? "select a carrier image"
    : source === "text" && message.length === 0
    ? "type a message"
    : source === "file" && !messageFile
    ? "attach a file to hide"
    : passphrase.length === 0
    ? "enter a passphrase"
    : overCapacity
    ? mode === "robust"
      ? `Payload exceeds Robust DCT limit (${messageBytes} > ${capacity} bytes). Switch to Stealth LSB Mode for larger files.`
      : `Payload exceeds carrier capacity (${messageBytes} > ${capacity} bytes). Increase bit depth or use a larger image.`
    : "";

  const canEncode =
    carrier &&
    (source === "text" ? message.length > 0 : !!messageFile) &&
    passphrase.length > 0 &&
    !overCapacity;

  const submit = async () => {
    setBusy(true);
    setError("");
    setResult(null);
    setDiff(null);
    setShowDiff(false);
    try {
      const res = await encodeImage({
        carrier,
        message,
        passphrase,
        messageFile: source === "file" ? messageFile : null,
        bitDepth,
        mode,
      });
      setResult(res);
      const base = carrier.name.replace(/\.(png|jpg|jpeg|bmp|gif|webp)$/i, "") || "carrier";
      setSavedName(`${base}-encoded.png`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const savePng = async () => {
    setSaving(true);
    setSaveNote("");
    try {
      if (isTauri()) {
        const path = await saveFileNative(
          savedName,
          result.blob,
          "PNG Image",
          ["png"]
        );
        setSaveNote(`saved to ${path}`);
      } else {
        downloadRef.current?.click();
      }
    } catch (err) {
      if (String(err).includes("cancelled")) {
        setSaveNote("save cancelled");
      } else {
        setSaveNote(`save failed: ${err}`);
      }
    } finally {
      setSaving(false);
    }
  };

  const copyImageToClipboard = async () => {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({ [result.blob.type || "image/png"]: result.blob }),
      ]);
      setSaveNote("image copied to clipboard!");
      setTimeout(() => setSaveNote(""), 2500);
    } catch (err) {
      setSaveNote("clipboard write failed: " + err);
    }
  };

  const toggleDiff = async () => {
    if (diff) {
      setShowDiff(!showDiff);
      return;
    }
    setDiffBusy(true);
    try {
      const { canvas, changed } = await buildDiffCanvas(originalUrl, result.url);
      setDiff({ url: canvas.toDataURL("image/png"), changed });
      setShowDiff(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setDiffBusy(false);
    }
  };

  const encodeStages = [
    { at: 15, text: "Reading carrier image..." },
    { at: 40, text: mode === "robust" ? "Encoding DCT blocks & RS-32 ECC..." : "Embedding payload into bit planes..." },
    { at: 75, text: "Securing with AES-256-GCM..." },
    { at: 92, text: "Generating output carrier..." },
  ];

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
          MULTI-IMAGE SHARDING
        </button>
      </div>

      {carrierType === "multi" ? (
        <ShardPanel defaultSubTab="encode" />
      ) : (
        <>
          <section className="panel-section">
            <h2 className="section-title">TRANSMISSION MODE</h2>
            <div className="mode-selector">
              <div
                className={`mode-card ${mode === "stealth" ? "active" : ""}`}
                onClick={() => setMode("stealth")}
              >
                <div className="mode-card-header">
                  <span className="mode-title">LSB STEALTH MODE</span>
                  <span className="mode-tag">MAX CAPACITY</span>
                </div>
                <p className="mode-desc">
                  High capacity for files &amp; text. Best for lossless transfer (PNG / Document mode).
                </p>
              </div>

              <div
                className={`mode-card ${mode === "robust" ? "active" : ""}`}
                onClick={() => setMode("robust")}
              >
                <div className="mode-card-header">
                  <span className="mode-title">ROBUST MODE</span>
                  <span className="mode-tag">WHATSAPP / JPEG</span>
                </div>
                <p className="mode-desc">
                  Protects messages against photo compression.
                </p>
              </div>
            </div>
          </section>

      <div className="panel-grid">
        <section className="panel-section">
          <h2 className="section-title">CARRIER IMAGE</h2>
          <DropZone file={carrier} onFile={onCarrier} label="Select carrier image" />
          {carrierMeta && (
            <div className="file-meta">
              <span>{carrier.name}</span>
              <span>
                {carrierMeta.width} &times; {carrierMeta.height}
              </span>
              <span className={overCapacity ? "meta-warn" : "meta-ok"}>
                capacity {capacity} bytes {mode === "robust" ? "(Robust)" : `(${bitDepth} LSB)`}
              </span>
            </div>
          )}
        </section>

        <section className="panel-section">
          <h2 className="section-title">PAYLOAD</h2>
          <div className="segmented">
            <button
              type="button"
              className={source === "text" ? "active" : ""}
              onClick={() => setSource("text")}
            >
              TEXT
            </button>
            <button
              type="button"
              className={source === "file" ? "active" : ""}
              onClick={() => setSource("file")}
            >
              FILE
            </button>
          </div>

          {source === "text" ? (
            <textarea
              className="text-input"
              rows={4}
              placeholder="Type the secret message to hide..."
              value={message}
              onChange={(e) => {
                setMessage(e.target.value);
                setError("");
              }}
            />
          ) : (
            <button
              type="button"
              className="file-input"
              onClick={() => document.getElementById("payload-file").click()}
            >
              <input
                id="payload-file"
                type="file"
                hidden
                onChange={(e) => {
                  setMessageFile(e.target.files[0]);
                  setError("");
                }}
              />
              {messageFile
                ? messageFile.name
                : "Attach a file to hide (image, text, any)..."}
            </button>
          )}
          <div className={`msg-count ${overCapacity ? "msg-count-warn" : ""}`}>
            {messageBytes} bytes {capacity !== null && ` / ${capacity} max`}
            {overCapacity && <span style={{ color: "#e74c3c", fontWeight: "bold" }}> (OVER CAPACITY)</span>}
          </div>
        </section>
      </div>

      <div className="panel-grid">
        {mode === "stealth" ? (
          <section className="panel-section">
            <div className="section-header-row">
              <h2 className="section-title">BIT DEPTH &amp; CAPACITY</h2>
              <span className="bit-depth-badge">{bitDepth} LSB / CHANNEL</span>
            </div>
            <div className="slider-control-row">
              <input
                type="range"
                min="1"
                max="4"
                step="1"
                value={bitDepth}
                onChange={(e) => setBitDepth(Number(e.target.value))}
                className="capacity-slider"
              />
              <div className="slider-labels">
                <span className={bitDepth === 1 ? "active" : ""}>1 LSB (Stealth)</span>
                <span className={bitDepth === 2 ? "active" : ""}>2 LSB (2x)</span>
                <span className={bitDepth === 3 ? "active" : ""}>3 LSB (3x)</span>
                <span className={bitDepth === 4 ? "active" : ""}>4 LSB (4x Max)</span>
              </div>
            </div>
          </section>
        ) : (
          <section className="panel-section">
            <div className="section-header-row">
              <h2 className="section-title">ROBUST PROTECTION</h2>
              <span className="bit-depth-badge" style={{ background: "rgba(52, 152, 219, 0.2)", color: "#3498db" }}>DCT + RS-32</span>
            </div>
            <div className="robust-quick-status">
              <span>Auto-scaled to 1280px &amp; protected with error correction</span>
            </div>
          </section>
        )}

        <section className="panel-section">
          <h2 className="section-title">PASSPHRASE &amp; ENCRYPTION</h2>
          <input
            type="password"
            className="text-input single"
            placeholder="Passphrase for AES-256-GCM"
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
            disabled={!canEncode || busy}
            onClick={submit}
          >
            {busy ? "ENCODING CARRIER..." : "ENCODE CARRIER"}
          </button>
          <ProgressBar busy={busy} stages={encodeStages} />
          {!busy && disabledHint && <div className="hint-box">{disabledHint}</div>}
        </section>
      </div>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <section className="panel-section result-box">
          <h2 className="section-title">RESULT</h2>
          <div className="result-content">
            <img
              className="result-preview"
              src={result.url}
              alt="encoded carrier"
              draggable={true}
              title="Drag image directly to desktop or other applications"
            />
            <div className="result-details">
              <p>
                <span className="result-label">Bits written</span>
                <span>{result.bits}</span>
              </p>
              <p>
                <span className="result-label">Payload bytes</span>
                <span>{Math.floor(result.bits / 8)}</span>
              </p>
              <p>
                <span className="result-label">Bit Depth</span>
                <span>{result.bitDepth || bitDepth} LSB / channel</span>
              </p>
              <p className="result-note">
                The output looks identical to the source. Alpha channel is protected and transparency is preserved.
              </p>
              <input
                type="text"
                className="text-input single"
                value={savedName}
                onChange={(e) => setSavedName(e.target.value)}
              />
              <div className="button-group-row">
                {isTauri() ? (
                  <button
                    type="button"
                    className="action-btn"
                    onClick={savePng}
                    disabled={saving}
                  >
                    {saving ? "SAVING..." : "SAVE PNG"}
                  </button>
                ) : (
                  <a
                    ref={downloadRef}
                    className="action-btn"
                    href={result.url}
                    download={savedName}
                  >
                    SAVE PNG
                  </a>
                )}
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={copyImageToClipboard}
                  title="Copy encoded PNG image to system clipboard"
                >
                  COPY TO CLIPBOARD
                </button>
              </div>
              {saveNote && <div className="hint-box">{saveNote}</div>}
            </div>
          </div>

          <h2 className="section-title">COMPARE</h2>
          <div className="compare-toolbar">
            <span className="compare-caption">
              {showDiff
                ? `${diff.changed} pixels modified — scattered by PRNG distribution`
                : "Drag the slider — original vs encoded"}
            </span>
            <button
              type="button"
              className={`ghost-btn ${showDiff ? "active" : ""}`}
              onClick={toggleDiff}
              disabled={diffBusy}
            >
              {diffBusy
                ? "SCANNING..."
                : showDiff
                ? "HIDE HIGHLIGHTS"
                : "HIGHLIGHT CHANGED PIXELS"}
            </button>
          </div>
          {showDiff && diff ? (
            <img className="compare-img diff-static" src={diff.url} alt="changed pixels" />
          ) : (
            <CompareSlider
              leftUrl={originalUrl}
              rightUrl={result.url}
              leftLabel="ORIGINAL"
              rightLabel="ENCODED"
            />
          )}
        </section>
      )}
      </>
      )}
    </div>
  );
}