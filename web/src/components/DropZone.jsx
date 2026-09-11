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
          <img
            src="/logo.png"
            alt="Cipher Canvas emblem"
            className="dropzone-logo-icon"
            draggable={false}
          />
          <span className="dropzone-label-title">{label}</span>
          <small className="dropzone-subhint">Drag &amp; drop carrier image or click to browse</small>
        </div>
      )}
    </div>
  );
}
