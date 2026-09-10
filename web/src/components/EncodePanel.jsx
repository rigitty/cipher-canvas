import { useEffect, useMemo, useRef, useState } from "react";
import DropZone from "./DropZone.jsx";
import CompareSlider from "./CompareSlider.jsx";
import { capacityBytes, encodeImage } from "../api.js";
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
  const [carrier, setCarrier] = useState(null);
  const [originalUrl, setOriginalUrl] = useState(null);
  const [carrierMeta, setCarrierMeta] = useState(null);
  const [source, setSource] = useState("text");
  const [message, setMessage] = useState("");
  const [messageFile, setMessageFile] = useState(null);
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [savedName, setSavedName] = useState("carrier.png");
  const [showDiff, setShowDiff] = useState(false);
  const [diff, setDiff] = useState(null);
  const [diffBusy, setDiffBusy] = useState(false);
  const downloadRef = useRef(null);

  const capacity = useMemo(
    () =>
      carrierMeta ? capacityBytes(carrierMeta.width, carrierMeta.height) : null,
    [carrierMeta]
  );

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
    ? "attach a message file"
    : passphrase.length === 0
    ? "enter a passphrase"
    : overCapacity
    ? `message exceeds capacity (${messageBytes} > ${capacity} bytes)`
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

  return (
    <div className="panel">
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
                capacity {capacity} bytes
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
              rows={7}
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
              {messageFile ? messageFile.name : "Attach a text file to hide..."}
            </button>
          )}
          <div className="msg-count">
            {messageBytes} bytes {capacity !== null && ` / ${capacity} max`}
          </div>
        </section>
      </div>

      <section className="panel-section">
        <h2 className="section-title">PASSPHRASE</h2>
        <input
          type="password"
          className="text-input single"
          placeholder="Required to decode the image"
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
          disabled={!canEncode || busy}
          onClick={submit}
        >
          {busy ? "ENCODING..." : "ENCODE IMAGE"}
        </button>
        {!busy && disabledHint && <div className="hint-box">{disabledHint}</div>}
      </section>

      {error && <div className="error-box">{error}</div>}

      {result && (
        <section className="panel-section result-box">
          <h2 className="section-title">RESULT</h2>
          <div className="result-content">
            <img className="result-preview" src={result.url} alt="encoded carrier" />
            <div className="result-details">
              <p>
                <span className="result-label">Bits written</span>
                <span>{result.bits}</span>
              </p>
              <p>
                <span className="result-label">Payload bytes</span>
                <span>{Math.floor(result.bits / 8)}</span>
              </p>
              <p className="result-note">
                The output looks identical to the source. Only the least significant
                bits were modified.
              </p>
              <input
                type="text"
                className="text-input single"
                value={savedName}
                onChange={(e) => setSavedName(e.target.value)}
              />
              <a
                ref={downloadRef}
                className="action-btn"
                href={result.url}
                download={savedName}
              >
                SAVE PNG
              </a>
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
    </div>
  );
}