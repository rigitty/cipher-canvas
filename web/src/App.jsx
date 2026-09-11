import { useState } from "react";
import TitleBar from "./components/TitleBar.jsx";
import EncodePanel from "./components/EncodePanel.jsx";
import DecodePanel from "./components/DecodePanel.jsx";
import InspectPanel from "./components/InspectPanel.jsx";

export default function App() {
  const [tab, setTab] = useState("encode");

  return (
    <div className="app">
      <TitleBar />

      <header className="app-header">
        <nav className="header-tabs">
          <button
            type="button"
            className={`tab-btn ${tab === "encode" ? "active" : ""}`}
            onClick={() => setTab("encode")}
          >
            ENCODE
          </button>
          <button
            type="button"
            className={`tab-btn ${tab === "decode" ? "active" : ""}`}
            onClick={() => setTab("decode")}
          >
            DECODE
          </button>
          <button
            type="button"
            className={`tab-btn ${tab === "inspect" ? "active" : ""}`}
            onClick={() => setTab("inspect")}
          >
            INSPECT
          </button>
        </nav>

      </header>
      <main className="content">
        <div className="tab-pane" style={{ display: tab === "encode" ? "block" : "none" }}>
          <EncodePanel />
        </div>
        <div className="tab-pane" style={{ display: tab === "decode" ? "block" : "none" }}>
          <DecodePanel />
        </div>
        <div className="tab-pane" style={{ display: tab === "inspect" ? "block" : "none" }}>
          <InspectPanel />
        </div>
      </main>
    </div>
  );
}