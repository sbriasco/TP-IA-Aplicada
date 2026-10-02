import { useRef } from "react";
import { formatVideoTime } from "../presentation/metrics";
import styles from "./VideoTimeRange.module.css";

interface VideoTimeRangeProps {
  durationSeconds: number;
  fromSeconds: number;
  toSeconds: number;
  onFromChange: (seconds: number) => void;
  onToChange: (seconds: number) => void;
}

function stepFor(durationSeconds: number): number {
  return durationSeconds <= 120 ? 0.1 : 1;
}

export function VideoTimeRange({
  durationSeconds,
  fromSeconds,
  toSeconds,
  onFromChange,
  onToChange,
}: VideoTimeRangeProps) {
  const duration = Math.max(durationSeconds, 0);
  const from = Math.min(Math.max(fromSeconds, 0), duration);
  const to = Math.min(Math.max(toSeconds, 0), duration);
  const span = duration > 0 ? duration : 1;
  const fromRatio = from / span;
  const toRatio = to / span;
  const railRef = useRef<HTMLSpanElement>(null);

  function secondsAt(clientX: number): number {
    const rail = railRef.current;
    if (!rail || duration === 0) return 0;
    const rect = rail.getBoundingClientRect();
    const ratio = rect.width === 0 ? 0 : (clientX - rect.left) / rect.width;
    const step = stepFor(duration);
    const raw = Math.min(duration, Math.max(0, ratio * duration));
    return Math.min(duration, Math.max(0, Math.round(raw / step) * step));
  }

  function move(which: "from" | "to", clientX: number) {
    const seconds = secondsAt(clientX);
    if (which === "from") onFromChange(Math.min(seconds, to));
    else onToChange(Math.max(seconds, from));
  }

  function bind(which: "from" | "to") {
    return {
      onPointerDown: (event: React.PointerEvent<HTMLButtonElement>) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        move(which, event.clientX);
      },
      onPointerMove: (event: React.PointerEvent<HTMLButtonElement>) => {
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
        move(which, event.clientX);
      },
      onKeyDown: (event: React.KeyboardEvent<HTMLButtonElement>) => {
        const step = stepFor(duration);
        const current = which === "from" ? from : to;
        let next = current;
        if (event.key === "ArrowRight" || event.key === "ArrowUp") next = current + step;
        else if (event.key === "ArrowLeft" || event.key === "ArrowDown") next = current - step;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = duration;
        else return;
        event.preventDefault();
        if (which === "from") onFromChange(Math.min(Math.max(next, 0), to));
        else onToChange(Math.max(Math.min(next, duration), from));
      },
    };
  }

  return (
    <div className={styles.range}>
      <div className={styles.labels}>
        <span>Inicio {formatVideoTime(from)}</span>
        <span>Video de {formatVideoTime(duration)}</span>
        <span>Fin {formatVideoTime(to)}</span>
      </div>
      <div className={styles.control}>
        <span ref={railRef} className={styles.rail} />
        <span
          className={styles.selection}
          style={{ left: `${fromRatio * 100}%`, right: `${(1 - toRatio) * 100}%` }}
        />
        <button
          type="button"
          className={styles.handle}
          style={{ left: `${fromRatio * 100}%` }}
          role="slider"
          aria-label="Inicio del tramo"
          aria-valuemin={0}
          aria-valuemax={duration}
          aria-valuenow={from}
          aria-valuetext={formatVideoTime(from)}
          {...bind("from")}
        />
        <button
          type="button"
          className={styles.handle}
          style={{ left: `${toRatio * 100}%`, zIndex: 2 }}
          role="slider"
          aria-label="Fin del tramo"
          aria-valuemin={0}
          aria-valuemax={duration}
          aria-valuenow={to}
          aria-valuetext={formatVideoTime(to)}
          {...bind("to")}
        />
        <input
          className={styles.native}
          tabIndex={-1}
          aria-hidden="true"
          type="range"
          aria-label="Inicio del tramo"
          min={0}
          max={duration}
          step={stepFor(duration)}
          value={from}
          onChange={(event) => onFromChange(Math.min(Number(event.target.value), to))}
        />
        <input
          className={styles.native}
          tabIndex={-1}
          aria-hidden="true"
          type="range"
          aria-label="Fin del tramo"
          min={0}
          max={duration}
          step={stepFor(duration)}
          value={to}
          onChange={(event) => onToChange(Math.max(Number(event.target.value), from))}
        />
      </div>
    </div>
  );
}
