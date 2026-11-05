import type { ChatResponse, ChatFigure } from "../api/chat";
import { formatMetric, LABEL_TEXT, METRIC_NAME } from "../presentation/metrics";
import styles from "./SessionChatPanel.module.css";

const EXTRA_NAMES: Record<string, string> = {
  funnel_observed_pass: "Funnel (pasos observados)",
  funnel_exposure: "Funnel (exposición)",
  funnel_stop: "Funnel (detención)",
  funnel_attention: "Funnel (atención estimada)",
  funnel_entries: "Funnel (entradas vinculadas)",
  funnel_observed_pass_to_exposure_rate: "Conversión de pasos a exposición",
  funnel_exposure_to_stop_rate: "Conversión de exposición a detención",
  funnel_stop_to_attention_rate: "Conversión de detención a atención",
  funnel_attention_to_linked_entry_rate: "Conversión de atención a entrada vinculada",
  group_count: "Grupos estimados",
  visit_count: "Posible compra estimada",
  peak: "Horario pico",
};

function formatChatMetric(code: string, value: number): string {
  return formatMetric(code.endsWith("_rate") ? "entry_rate" : code, value);
}

export function AgentAnswer({ answer }: { answer: ChatResponse }) {
  function figureText(figure: ChatFigure): string {
    if (figure.code.includes("__")) {
      return `${figure.code.split("__")[0]}: ${
        figure.availability === "available" && figure.value !== null
          ? formatChatMetric(figure.code.split("__")[0], figure.value)
          : "no disponible"
      }`;
    }
    if (figure.code === "peak") {
      const peak =
        figure.availability === "available" &&
        figure.start_seconds != null &&
        figure.track_count != null
          ? `${figure.start_seconds} s · ${figure.track_count} tracks`
          : "no disponible";
      return `Horario pico: ${peak}`;
    }
    const value =
      figure.availability === "available" && figure.value !== null
        ? formatChatMetric(figure.code, figure.value)
        : "no disponible";
    const label = LABEL_TEXT[figure.label];
    const name = METRIC_NAME[figure.code] ?? EXTRA_NAMES[figure.code] ?? figure.code;
    const estimate = figure.estimation ? " · estimación" : "";
    return name + ": " + value + (label ? " · " + label : "") + estimate;
  }

  const scopeLabel =
    answer.scope === "comparison"
      ? `contraste${answer.comparison ? ` · eje ${answer.comparison.axis}` : ""}`
      : answer.scope === "whole_session"
        ? "toda la sesión"
        : "Ayuda de FlowSight";

  return (
    <section className={styles.answer} aria-label="Respuesta">
      <span className={styles.author}>Agente FlowSight</span>
      <p role={answer.status === "error" ? "alert" : undefined}>{answer.message}</p>
      {answer.status === "answered" && (
        <>
          <small>
            {answer.shop_name ? answer.shop_name + " · " : ""}
            {scopeLabel}
            {answer.comparison && answer.comparison.column_labels.length > 0
              ? ` · ${answer.comparison.column_labels.join(" vs ")}`
              : ""}
          </small>
          {answer.figures.length > 0 && (
            <ul className={styles.figures}>
              {answer.figures
                .filter((figure) => !figure.code.includes("__") || answer.scope === "comparison")
                .slice(0, answer.scope === "comparison" ? 12 : 20)
                .map((figure) => (
                  <li key={figure.code}>{figureText(figure)}</li>
                ))}
            </ul>
          )}
        </>
      )}
      {answer.status === "needs_clarification" && (
        <small>Hace falta aclarar la sesión, la zona o el contraste.</small>
      )}
    </section>
  );
}
