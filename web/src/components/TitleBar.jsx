import { useEffect, useState } from "react";

const isTauri = () => "__TAURI_INTERNALS__" in window;

async function getWindow() {
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  return getCurrentWindow();
}

function IconButton({ label, onClick, children }) {
  return (
    <button
      type="button"
      className="titlebar-btn"
      aria-label={label}
      title={label}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export default function TitleBar() {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    if (!isTauri()) return;
    let disposed = false;
    getWindow().then((win) => {
      if (disposed) return;
      win.isMaximized().then(setMaximized);
      const unlisten = win.onResized(() => {
        win.isMaximized().then(setMaximized);
      });
      unlisten.then((fn) => {
        if (disposed) fn();
      });
    });
    return () => {
      disposed = true;
    };
  }, []);

  const minimize = () => getWindow().then((w) => w.minimize());
  const toggleMaximize = () =>
    getWindow().then((w) =>
      w.isMaximized().then((is) => (is ? w.unmaximize() : w.maximize()))
    );
  const close = () => getWindow().then((w) => w.close());

  return (
    <header className="titlebar">
      <div className="titlebar-brand" data-tauri-drag-region>
        <img
          className="brand-logo"
          src="/logo-title.png"
          alt="Cipher Canvas logo"
          draggable={false}
        />
        <span className="brand-name">CIPHER CANVAS</span>
      </div>
      <div className="titlebar-spacer" data-tauri-drag-region />
      <div className="titlebar-controls">
        <IconButton label="Minimize" onClick={minimize}>
          <svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">
            <line x1="1" y1="5" x2="9" y2="5" stroke="currentColor" strokeWidth="1" />
          </svg>
        </IconButton>
        <IconButton label={maximized ? "Restore" : "Maximize"} onClick={toggleMaximize}>
          {maximized ? (
            <svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">
              <rect x="2" y="1" width="7" height="7" fill="none" stroke="currentColor" strokeWidth="1" />
              <path d="M1 4h4v5H1z" fill="none" stroke="currentColor" strokeWidth="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">
              <rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" strokeWidth="1" />
            </svg>
          )}
        </IconButton>
        <IconButton label="Close" onClick={close}>
          <svg viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">
            <path d="M1 1l8 8M9 1l-8 8" stroke="currentColor" strokeWidth="1" />
          </svg>
        </IconButton>
      </div>
    </header>
  );
}
