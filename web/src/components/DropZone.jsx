import { useEffect, useRef, useState } from "react";

export default function DropZone({ file, onFile, label }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const readFile = (f) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) {
      alert(`${f.name} is not an image file`);
      return;
    }
    onFile(f);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    readFile(e.dataTransfer.files[0]);
  };

  const handlePasteEvent = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        const pastedFile = item.getAsFile();
        if (pastedFile) {
          e.preventDefault();
          readFile(pastedFile);
          return;
        }
      }
    }
  };

  const handleClipboardClick = async (e) => {
    e.stopPropagation();
    try {
      if (navigator.clipboard?.read) {
        const items = await navigator.clipboard.read();
        for (const item of items) {
          const imageType = item.types.find((t) => t.startsWith("image/"));
          if (imageType) {
            const blob = await item.getType(imageType);
            const pastedFile = new File([blob], "pasted-image.png", { type: imageType });
            readFile(pastedFile);
            return;
          }
        }
      }
      alert("No image found in clipboard. Use Ctrl+V or copy an image first.");
    } catch {
      alert("Clipboard access denied or unavailable. Press Ctrl+V directly.");
    }
  };

  useEffect(() => {
    window.addEventListener("paste", handlePasteEvent);
    return () => window.removeEventListener("paste", handlePasteEvent);
  }, []);

  return (
    <div
      className={`dropzone ${dragging ? "is-dragging" : ""}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => readFile(e.target.files[0])}
      />
      {file ? (
        <img
          className="dropzone-preview"
          src={URL.createObjectURL(file)}
          alt="carrier preview"
          draggable={true}
        />
      ) : (
        <div className="dropzone-empty">
          <img
            src="/logo.png"
            alt="Cipher Canvas emblem"
            className="dropzone-logo-icon"
            draggable={false}
          />
          <span className="dropzone-label-title">{label}</span>
          <small className="dropzone-subhint">
            Drag &amp; drop carrier image, click to browse, or press <code>Ctrl+V</code>
          </small>
          <button
            type="button"
            className="paste-clipboard-btn"
            onClick={handleClipboardClick}
            title="Paste image from system clipboard"
          >
            📋 PASTE FROM CLIPBOARD
          </button>
        </div>
      )}
    </div>
  );
}
