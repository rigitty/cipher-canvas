import { useEffect, useState } from "react";

export default function ProgressBar({ busy, stages, onFinish, onCancel }) {
  const [percent, setPercent] = useState(0);
  const [currentStage, setCurrentStage] = useState(stages?.[0]?.text || "Processing...");

  useEffect(() => {
    if (!busy) {
      if (percent > 0 && percent < 100) {
        setPercent(100);
        setCurrentStage("Complete!");
        const timer = setTimeout(() => {
          setPercent(0);
          if (onFinish) onFinish();
        }, 250);
        return () => clearTimeout(timer);
      } else {
        setPercent(0);
      }
      return;
    }

    setPercent(8);
    const stageList = stages || [
      { at: 15, text: "Initializing..." },
      { at: 45, text: "Processing carrier data..." },
      { at: 75, text: "Applying cryptographic transforms..." },
      { at: 92, text: "Finalizing..." },
    ];

    setCurrentStage(stageList[0]?.text || "Processing...");

    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      setPercent((prev) => {
        if (prev >= 92) return 92;
        const next = Math.min(92, Math.floor(10 + 82 * (1 - Math.exp(-elapsed / 1100))));
        for (let i = stageList.length - 1; i >= 0; i--) {
          if (next >= stageList[i].at) {
            setCurrentStage(stageList[i].text);
            break;
          }
        }
        return next;
      });
    }, 50);

    return () => clearInterval(interval);
  }, [busy]);

  if (!busy && percent === 0) return null;

  return (
    <div className="progress-container">
      <div className="progress-header">
        <div className="progress-stage-wrap">
          {busy && <span className="progress-spinner" />}
          <span className="progress-stage">{currentStage}</span>
        </div>
        <div className="progress-actions-wrap">
          <span className="progress-value">{Math.round(percent)}%</span>
          {busy && onCancel && (
            <button
              type="button"
              className="progress-cancel-btn"
              onClick={onCancel}
              title="Cancel ongoing operation"
            >
              CANCEL
            </button>
          )}
        </div>
      </div>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
