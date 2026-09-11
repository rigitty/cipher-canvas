import { useEffect, useMemo, useRef, useState } from "react";
import ProgressBar from "./ProgressBar.jsx";
import EntropyMeter from "./EntropyMeter.jsx";
import {
  capacityBytes,
  encodeSharded,
  decodeSharded,
  isTauri,
  saveFileNative,
} from "../api.js";

const IMAGE_EXT_REGEX = /\.(png|jpe?g|bmp|webp|gif|tiff?)$/i;

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

export default function ShardPanel({ defaultSubTab = "encode" }) {
  const [subTab, setSubTab] = useState(defaultSubTab); // "encode" | "decode"

  useEffect(() => {
    setSubTab(defaultSubTab);
  }, [defaultSubTab]);

  // ----- Encode State -----
  const [carriers, setCarriers] = useState([]);
  const [carriersMeta, setCarriersMeta] = useState([]);
  const [payloadFile, setPayloadFile] = useState(null);
  const [payloadText, setPayloadText] = useState("");
  const [payloadType, setPayloadType] = useState("file"); // "file" | "text"
  const [passphrase, setPassphrase] = useState("");
  const [bitDepth, setBitDepth] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [encodeResult, setEncodeResult] = useState(null);
  const [savingZip, setSavingZip] = useState(false);
  const [zipNote, setZipNote] = useState("");

  // ----- Decode State -----
  const [shardFiles, setShardFiles] = useState([]);
  const [decodePassphrase, setDecodePassphrase] = useState("");
  const [decodeBusy, setDecodeBusy] = useState(false);
  const [decodeError, setDecodeError] = useState("");
  const [decodeResult, setDecodeResult] = useState(null);
  const [saveName, setSaveName] = useState("");
  const [savingDecoded, setSavingDecoded] = useState(false);
  const [saveDecodedNote, setSaveDecodedNote] = useState("");

  const fileInputRef = useRef(null);
  const shardInputRef = useRef(null);

  // --- Handlers for Encode Carriers ---
  const handleAddCarriers = async (e) => {
    const files = Array.from(e.target.files || []).filter((f) =>
      IMAGE_EXT_REGEX.test(f.name)
    );
    if (files.length > 0) {
      const newMetas = await Promise.all(
        files.map(async (f) => {
          try {
            return await readImageSize(f);
          } catch {
            return { width: 800, height: 600 };
          }
        })
      );
      setCarriers((prev) => [...prev, ...files]);
      setCarriersMeta((prev) => [...prev, ...newMetas]);
      setError("");
    }
  };

  const removeCarrier = (idx) => {
    setCarriers((prev) => prev.filter((_, i) => i !== idx));
    setCarriersMeta((prev) => prev.filter((_, i) => i !== idx));
  };

  const payloadSizeBytes = useMemo(() => {
    if (payloadType === "file" && payloadFile) return payloadFile.size;
    if (payloadType === "text") return new TextEncoder().encode(payloadText).length;
    return 0;
  }, [payloadType, payloadFile, payloadText]);

  // Combined capacity of all selected carrier images
  const totalCapacityBytes = useMemo(() => {
    if (carriersMeta.length === 0) return 0;
    return carriersMeta.reduce((acc, meta) => {
      // Stego overhead + 32-byte shard header + 44-byte AES + 1.4x RS-ECC
      const slots = meta.width * meta.height * 3;
      const availSlots = Math.max(0, slots - 72);
      const maxSealed = Math.floor((availSlots * bitDepth) / 8);
      const usable = Math.max(0, Math.floor((maxSealed - 64) / 1.45) - 32 - 20);
      return acc + usable;
    }, 0);
  }, [carriersMeta, bitDepth]);

  const isOverCapacity = payloadSizeBytes > 0 && totalCapacityBytes > 0 && payloadSizeBytes > totalCapacityBytes;

  const handleAddShards = (e) => {
    const files = Array.from(e.target.files || []).filter((f) =>
      IMAGE_EXT_REGEX.test(f.name)
    );
    if (files.length > 0) {
      setShardFiles((prev) => [...prev, ...files]);
      setDecodeError("");
    }
  };

  const removeShard = (idx) => {
    setShardFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  // --- Submit Shard Encoding ---
  const handleEncodeSubmit = async () => {
    if (carriers.length < 2) {
      setError("Please add at least 2 carrier images for sharding.");
      return;
    }
    if (payloadType === "file" && !payloadFile) {
      setError("Please select a payload file to hide.");
      return;
    }
    if (payloadType === "text" && !payloadText) {
      setError("Please enter a secret message.");
      return;
    }
    if (!passphrase) {
      setError("Please enter an encryption passphrase.");
      return;
    }

    setBusy(true);
    setError("");
    setEncodeResult(null);
    setZipNote("");

    try {
      const res = await encodeSharded({
        carriers,
        message: payloadText,
        messageFile: payloadType === "file" ? payloadFile : null,
        passphrase,
        bitDepth,
      });
      setEncodeResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  // --- Submit Shard Decoding ---
  const handleDecodeSubmit = async () => {
    if (shardFiles.length < 2) {
      setDecodeError("Please upload at least 2 shard images to assemble.");
      return;
    }
    if (!decodePassphrase) {
      setDecodeError("Please enter the passphrase used during sharding.");
      return;
    }

    setDecodeBusy(true);
    setDecodeError("");
    setDecodeResult(null);
    setSaveDecodedNote("");

    try {
      const res = await decodeSharded({
        shards: shardFiles,
        passphrase: decodePassphrase,
      });
      setDecodeResult(res);
      setSaveName(res.filename);
    } catch (err) {
      setDecodeError(err.message);
    } finally {
      setDecodeBusy(false);
    }
  };

  const saveZip = async () => {
    if (!encodeResult) return;
    setSavingZip(true);
    setZipNote("");
    try {
      if (isTauri()) {
        const path = await saveFileNative(
          encodeResult.filename,
          encodeResult.blob,
          "ZIP Archive",
          ["zip"]
        );
        setZipNote(`Saved to ${path}`);
      } else {
        const a = document.createElement("a");
        a.href = encodeResult.url;
        a.download = encodeResult.filename;
        a.click();
      }
    } catch (err) {
      setZipNote(String(err).includes("cancelled") ? "Save cancelled" : `Save failed: ${err}`);
    } finally {
      setSavingZip(false);
    }
  };

  const saveDecodedFile = async () => {
    if (!decodeResult) return;
    setSavingDecoded(true);
    setSaveDecodedNote("");
    try {
      if (isTauri()) {
        const path = await saveFileNative(saveName, decodeResult.blob, null, null);
        setSaveDecodedNote(`Saved to ${path}`);
      } else {
        const a = document.createElement("a");
        a.href = decodeResult.url;
        a.download = saveName;
        a.click();
      }
    } catch (err) {
      setSaveDecodedNote(String(err).includes("cancelled") ? "Save cancelled" : `Save failed: ${err}`);
    } finally {
      setSavingDecoded(false);
    }
  };

  const encodeStages = [
    { at: 20, text: "Calculating proportional image capacities..." },
    { at: 45, text: "Encrypting and chunking payload with CCSH headers..." },
    { at: 75, text: "Embedding shard slices across carrier images..." },
    { at: 92, text: "Packaging output archive..." },
  ];

  const decodeStages = [
    { at: 20, text: "Scanning shard carriers..." },
    { at: 50, text: "Verifying Group IDs & shard integrity CRC32..." },
    { at: 75, text: "Assembling chunk sequence & Reed-Solomon check..." },
    { at: 92, text: "Decrypting assembled payload..." },
  ];

  return (
    <div className="panel">
      {subTab === "encode" ? (
        <div className="shard-content-container">
          <div className="panel-grid">
            {/* Left: Carrier Images Selection */}
            <section className="panel-section">
              <div className="section-header-row">
                <h2 className="section-title">CARRIER IMAGES ({carriers.length})</h2>
                <button
                  type="button"
                  className="ghost-btn compact"
                  onClick={() => fileInputRef.current?.click()}
                >
                  + ADD CARRIERS
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept="image/*"
                  hidden
                  onChange={handleAddCarriers}
                />
              </div>

              {carriers.length === 0 ? (
                <div
                  className="shard-empty-dropzone"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <img src="/logo.png" alt="logo" className="dropzone-logo-icon" />
                  <span className="dropzone-label-title">Select 2 or more carrier images</span>
                  <small className="dropzone-subhint">
                    Large files are automatically divided and encrypted across all chosen images.
                  </small>
                </div>
              ) : (
                <div className="shard-list-grid">
                  {carriers.map((f, i) => (
                    <div key={i} className="shard-item-card">
                      <img
                        src={URL.createObjectURL(f)}
                        alt={f.name}
                        className="shard-thumb"
                      />
                      <div className="shard-item-info">
                        <span className="shard-name">#{i + 1} {f.name}</span>
                        <span className="shard-size">{(f.size / 1024).toFixed(1)} KB</span>
                      </div>
                      <button
                        type="button"
                        className="shard-remove-btn"
                        onClick={() => removeCarrier(i)}
                        title="Remove image"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {carriers.length > 0 && (
                <div className="file-meta" style={{ marginTop: "10px" }}>
                  <span>{carriers.length} Carrier Images</span>
                  <span className={isOverCapacity ? "meta-warn" : "meta-ok"}>
                    Total Capacity: {(totalCapacityBytes / (1024 * 1024)).toFixed(2)} MB ({totalCapacityBytes.toLocaleString()} B)
                  </span>
                </div>
              )}
            </section>

            {/* Right: Payload & Encryption */}
            <section className="panel-section">
              <h2 className="section-title">PAYLOAD TO SHARD</h2>
              <div className="segmented">
                <button
                  type="button"
                  className={payloadType === "file" ? "active" : ""}
                  onClick={() => setPayloadType("file")}
                >
                  FILE (ANY SIZE)
                </button>
                <button
                  type="button"
                  className={payloadType === "text" ? "active" : ""}
                  onClick={() => setPayloadType("text")}
                >
                  TEXT
                </button>
              </div>

              {payloadType === "file" ? (
                <button
                  type="button"
                  className="file-input"
                  onClick={() => document.getElementById("shard-payload-file").click()}
                >
                  <input
                    id="shard-payload-file"
                    type="file"
                    hidden
                    onChange={(e) => {
                      setPayloadFile(e.target.files[0]);
                      setError("");
                    }}
                  />
                  {payloadFile ? `${payloadFile.name} (${(payloadFile.size / 1024).toFixed(1)} KB)` : "Attach file to split across carriers..."}
                </button>
              ) : (
                <textarea
                  className="text-input"
                  rows={3}
                  placeholder="Secret message or large text to distribute..."
                  value={payloadText}
                  onChange={(e) => setPayloadText(e.target.value)}
                />
              )}

              <div className={`msg-count ${isOverCapacity ? "msg-count-warn" : ""}`}>
                {payloadSizeBytes > 0 && (
                  <span>
                    Payload: {(payloadSizeBytes / (1024 * 1024)).toFixed(2)} MB ({payloadSizeBytes.toLocaleString()} B)
                    {totalCapacityBytes > 0 && ` / Max Total: ${(totalCapacityBytes / (1024 * 1024)).toFixed(2)} MB`}
                  </span>
                )}
                {isOverCapacity && (
                  <div style={{ color: "#e74c3c", fontWeight: "bold", marginTop: "4px" }}>
                    Payload ({((payloadSizeBytes) / (1024 * 1024)).toFixed(2)} MB) exceeds combined capacity of selected images ({((totalCapacityBytes) / (1024 * 1024)).toFixed(2)} MB).
                    <br />
                    Need <strong>{(((payloadSizeBytes - totalCapacityBytes)) / (1024 * 1024)).toFixed(2)} MB</strong> more carrier capacity. Please add higher resolution images or increase LSB depth.
                  </div>
                )}
              </div>

              <h2 className="section-title" style={{ marginTop: "14px" }}>PASSPHRASE</h2>
              <input
                type="password"
                className="text-input single"
                placeholder="Passphrase for shard distribution & encryption"
                value={passphrase}
                autoComplete="off"
                onChange={(e) => setPassphrase(e.target.value)}
              />
              <EntropyMeter passphrase={passphrase} />

              <div className="section-header-row" style={{ marginTop: "10px" }}>
                <span className="bit-depth-badge">{bitDepth} LSB PER CHANNEL</span>
                <input
                  type="range"
                  min="1"
                  max="4"
                  step="1"
                  value={bitDepth}
                  onChange={(e) => setBitDepth(Number(e.target.value))}
                  className="capacity-slider"
                  style={{ width: "140px" }}
                />
              </div>

              <button
                type="button"
                className="action-btn"
                disabled={carriers.length < 2 || !passphrase || isOverCapacity || busy}
                onClick={handleEncodeSubmit}
                style={{ marginTop: "14px" }}
              >
                {busy ? "SPLITTING & ENCRYPTING..." : `GENERATE ${carriers.length || 0} SHARDS (ZIP)`}
              </button>
              <ProgressBar busy={busy} stages={encodeStages} />
            </section>
          </div>

          {error && <div className="error-box">{error}</div>}

          {encodeResult && (
            <section className="panel-section result-box">
              <h2 className="section-title">SHARDING COMPLETE</h2>
              <div className="robust-info-card">
                <div className="robust-info-header">
                  <span>{encodeResult.shardCount} Stego Shards Successfully Generated</span>
                </div>
                <p className="robust-info-text">
                  Your payload was divided into {encodeResult.shardCount} encrypted segments with embedded integrity checksums (CCSH headers).
                  Recipients will need all {encodeResult.shardCount} image files and the passphrase to reconstruct the original payload.
                </p>
                <div className="button-group-row" style={{ marginTop: "8px" }}>
                  <button
                    type="button"
                    className="action-btn"
                    onClick={saveZip}
                    disabled={savingZip}
                  >
                    {savingZip ? "SAVING ZIP..." : `DOWNLOAD ALL ${encodeResult.shardCount} SHARDS (.ZIP)`}
                  </button>
                </div>
                {zipNote && <div className="hint-box">{zipNote}</div>}
              </div>
            </section>
          )}
        </div>
      ) : (
        /* Decode (Assemble) Sub-tab */
        <div className="shard-content-container">
          <div className="panel-grid">
            <section className="panel-section">
              <div className="section-header-row">
                <h2 className="section-title">UPLOAD SHARDS ({shardFiles.length})</h2>
                <button
                  type="button"
                  className="ghost-btn compact"
                  onClick={() => shardInputRef.current?.click()}
                >
                  + ADD SHARD IMAGES
                </button>
                <input
                  ref={shardInputRef}
                  type="file"
                  multiple
                  accept="image/*"
                  hidden
                  onChange={handleAddShards}
                />
              </div>

              {shardFiles.length === 0 ? (
                <div
                  className="shard-empty-dropzone"
                  onClick={() => shardInputRef.current?.click()}
                >
                  <img src="/logo.png" alt="logo" className="dropzone-logo-icon" />
                  <span className="dropzone-label-title">Select all shard images</span>
                  <small className="dropzone-subhint">
                    Add the image files that make up the sharded container. Order does not matter.
                  </small>
                </div>
              ) : (
                <div className="shard-list-grid">
                  {shardFiles.map((f, i) => (
                    <div key={i} className="shard-item-card">
                      <img
                        src={URL.createObjectURL(f)}
                        alt={f.name}
                        className="shard-thumb"
                      />
                      <div className="shard-item-info">
                        <span className="shard-name">#{i + 1} {f.name}</span>
                        <span className="shard-size">{(f.size / 1024).toFixed(1)} KB</span>
                      </div>
                      <button
                        type="button"
                        className="shard-remove-btn"
                        onClick={() => removeShard(i)}
                        title="Remove shard"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="panel-section">
              <h2 className="section-title">PASSPHRASE</h2>
              <input
                type="password"
                className="text-input single"
                placeholder="Passphrase used during sharding"
                value={decodePassphrase}
                autoComplete="off"
                onChange={(e) => setDecodePassphrase(e.target.value)}
              />
              <EntropyMeter passphrase={decodePassphrase} />

              <button
                type="button"
                className="action-btn"
                disabled={shardFiles.length < 2 || !decodePassphrase || decodeBusy}
                onClick={handleDecodeSubmit}
                style={{ marginTop: "14px" }}
              >
                {decodeBusy ? "VALIDATING & ASSEMBLING..." : `ASSEMBLE ${shardFiles.length} SHARDS`}
              </button>
              <ProgressBar busy={decodeBusy} stages={decodeStages} />
              <div className="robust-tip-box" style={{ marginTop: "10px" }}>
                Auto-sorts shards by sequence index and verifies cryptographic CRC checksums.
              </div>
            </section>
          </div>

          {decodeError && <div className="error-box">{decodeError}</div>}

          {decodeResult && (
            <section className="panel-section result-box">
              <h2 className="section-title">REASSEMBLED PAYLOAD</h2>
              <div className="file-meta">
                <span>{decodeResult.filename}</span>
                <span>{decodeResult.size} bytes</span>
                <span>{decodeResult.shardCount} Shards Combined</span>
                <span>Group ID: {decodeResult.groupId ? decodeResult.groupId.slice(0, 8) : ""}...</span>
              </div>

              {decodeResult.type?.startsWith("video/") || /\.(mp4|webm|mov|mkv)$/i.test(decodeResult.filename) ? (
                <div style={{ marginTop: "12px", marginBottom: "12px" }}>
                  <video
                    src={decodeResult.url}
                    controls
                    style={{ width: "100%", maxHeight: "280px", borderRadius: "6px", background: "#000" }}
                  />
                </div>
              ) : decodeResult.type?.startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(decodeResult.filename) ? (
                <img
                  src={decodeResult.url}
                  alt="extracted"
                  style={{ width: "100%", maxHeight: "240px", objectFit: "contain", borderRadius: "6px", margin: "12px 0" }}
                />
              ) : decodeResult.type?.startsWith("audio/") || /\.(mp3|wav|ogg|m4a)$/i.test(decodeResult.filename) ? (
                <audio src={decodeResult.url} controls style={{ width: "100%", margin: "12px 0" }} />
              ) : null}

              {decodeResult.text !== null ? (
                <pre className="message-output">{decodeResult.text}</pre>
              ) : (
                <p className="result-note">
                  Binary payload ({decodeResult.filename}) restored with 100% integrity. Save to disk to access.
                </p>
              )}

              <input
                type="text"
                className="text-input single"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
              />
              <div className="button-group-row">
                <button
                  type="button"
                  className="action-btn"
                  onClick={saveDecodedFile}
                  disabled={savingDecoded}
                >
                  {savingDecoded ? "SAVING FILE..." : "SAVE RECOVERED FILE"}
                </button>
              </div>
              {saveDecodedNote && <div className="hint-box">{saveDecodedNote}</div>}
            </section>
          )}
        </div>
      )}
    </div>
  );
}