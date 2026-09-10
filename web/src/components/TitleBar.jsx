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
        <svg className="brand-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path d="M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3z" fill="var(--accent)" />
          <rect x="9" y="9" width="6" height="6" rx="1" fill="#0d0d0f" />
          <rect x="11" y="7" width="2" height="3" fill="#0d0d0f" />
        </svg>
        <span className="brand-name">CIPHER CANVAS</span>
        <span className="brand-version">v1.0</span>
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
