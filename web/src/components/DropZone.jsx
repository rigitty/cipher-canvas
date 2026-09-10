import { useRef, useState } from "react";

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
        <img className="dropzone-preview" src={URL.createObjectURL(file)} alt="carrier preview" />
      ) : (
        <div className="dropzone-empty">
          <svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
            <path
              d="M12 16V4m0 0 4 4m-4-4-4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>{label}</span>
          <small>drag &amp; drop or click to browse</small>
        </div>
      )}
    </div>
  );
}
