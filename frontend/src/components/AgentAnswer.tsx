import type { ChatResponse, ChatFigure } from "../api/chat";
import { formatMetric, LABEL_TEXT, METRIC_NAME } from "../presentation/metrics";
import styles from "./SessionChatPanel.module.css";

export function AgentAnswer({ answer }: { answer: ChatResponse }) {
  function figureText(figure: ChatFigure): string {
    if (figure.code === "peak") {
      const peak = figure.availability === "available" && figure.start_seconds != null && figure.track_count != null
        ? `${figure.start_seconds} s · ${figure.track_count} tracks`
        : "no disponible";
      return `Horario pico: ${peak}`;
    }
    const value = figure.availability === "available" && figure.value !== null ? formatMetric(figure.code, figure.value) : "no disponible";
    const label = LABEL_TEXT[figure.label];
    return (METRIC_NAME[figure.code] ?? figure.code) + ": " + value + (label ? " · " + label : "");
  }
  return (
    <section className={styles.answer} aria-label="Respuesta">
      <span className={styles.author}>Agente FlowSight</span>
      <p role={answer.status === "error" ? "alert" : undefined}>{answer.message}</p>
      {answer.status === "answered" && <>
        <small>{answer.shop_name ? answer.shop_name + " · " : ""}toda la sesión</small>
        {answer.figures.length > 0 && <ul className={styles.figures}>{answer.figures.map((figure) => <li key={figure.code}>{figureText(figure)}</li>)}</ul>}
      </>}
    </section>
  );
}
