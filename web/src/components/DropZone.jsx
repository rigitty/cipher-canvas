import { useEffect, useRef, useState } from "react";
import { isTauri, readNativeFile } from "../api.js";

const IMAGE_EXT_REGEX = /\.(png|jpe?g|bmp|webp|gif|tiff?)$/i;

export default function DropZone({ file, onFile, label }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const dropzoneRef = useRef(null);

  const readFile = (f) => {
    if (!f) return;
    const isImg = (f.type && f.type.startsWith("image/")) || IMAGE_EXT_REGEX.test(f.name);
    if (!isImg) {
      alert(`${f.name} is not a supported image file`);
      return;
    }
    onFile(f);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  };

  const onDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    const droppedFiles = e.dataTransfer?.files;
    if (droppedFiles && droppedFiles.length > 0) {
      readFile(droppedFiles[0]);
    }
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
      alert("Clipboard access unavailable. Press Ctrl+V directly.");
    }
  };

  useEffect(() => {
    window.addEventListener("paste", handlePasteEvent);

    // Window-level drag suppression
    const preventWindowDrag = (e) => {
      e.preventDefault();
    };
    window.addEventListener("dragover", preventWindowDrag);
    window.addEventListener("drop", preventWindowDrag);

    // Tauri native file drag-drop listener
    let unlistenTauri = null;
    if (isTauri()) {
      import("@tauri-apps/api/webviewWindow")
        .then(({ getCurrentWebviewWindow }) => {
          return getCurrentWebviewWindow().onDragDropEvent((event) => {
            if (event.payload.type === "over") {
              setDragging(true);
            } else if (event.payload.type === "leave" || event.payload.type === "cancel") {
              setDragging(false);
            } else if (event.payload.type === "drop") {
              setDragging(false);
              const paths = event.payload.paths;
              if (paths && paths.length > 0) {
                const targetPath = paths[0];
                if (IMAGE_EXT_REGEX.test(targetPath)) {
                  readNativeFile(targetPath)
                    .then(onFile)
                    .catch((err) => console.error("failed reading dropped file:", err));
                }
              }
            }
          });
        })
        .then((fn) => {
          unlistenTauri = fn;
        })
        .catch(() => {});
    }

    return () => {
      window.removeEventListener("paste", handlePasteEvent);
      window.removeEventListener("dragover", preventWindowDrag);
      window.removeEventListener("drop", preventWindowDrag);
      if (unlistenTauri) unlistenTauri();
    };
  }, []);

  return (
    <div
      ref={dropzoneRef}
      className={`dropzone ${dragging ? "is-dragging" : ""}`}
      onClick={() => inputRef.current?.click()}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
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
            PASTE FROM CLIPBOARD
          </button>
        </div>
      )}
    </div>
  );
}
