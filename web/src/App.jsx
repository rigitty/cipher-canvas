import { useEffect, useState } from "react";
import TitleBar from "./components/TitleBar.jsx";
import EncodePanel from "./components/EncodePanel.jsx";
import DecodePanel from "./components/DecodePanel.jsx";
import { healthCheck } from "./api.js";

export default function App() {
  const [tab, setTab] = useState("encode");
  const [engine, setEngine] = useState("checking");

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const info = await healthCheck();
        if (alive) setEngine(info.status === "ok" ? "online" : "offline");
      } catch {
        if (alive) setEngine("offline");
      }
    };
    poll();
    const timer = setInterval(poll, 5000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="app">
      <TitleBar />
      <nav className="tabbar">
        <button
          type="button"
          className={`tab ${tab === "encode" ? "active" : ""}`}
          onClick={() => setTab("encode")}
        >
          ENCODE
        </button>
        <button
          type="button"
          className={`tab ${tab === "decode" ? "active" : ""}`}
          onClick={() => setTab("decode")}
        >
          DECODE
        </button>
      </nav>
      {engine === "offline" && (
        <div className="offline-banner">
          engine server is offline — operations are disabled. start{" "}
          <code>server.py</code> on port 8000 and relaunch.
        </div>
      )}
      <main className="content">
        {tab === "encode" ? <EncodePanel /> : <DecodePanel />}
      </main>
      <footer className="statusbar">
        <span className="engine-dot" data-status={engine} />
        <span>engine {engine}</span>
        <span className="statusbar-sep" />
        <span>AES-256-GCM &middot; LSB &middot; PRNG</span>
      </footer>
    </div>
  );
}