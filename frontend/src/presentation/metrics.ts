export const METRIC_NAME: Record<string, string> = {
  traffic_total: "Tráfico", store_pass: "Pasos", entries: "Entradas", exits: "Salidas",
  entry_rate: "Tasa de ingreso", dwell_mean_seconds: "Permanencia media",
  dwell_median_seconds: "Permanencia mediana", visible_occupancy: "Ocupación visible",
};

export const METRIC_DESCRIPTION: Record<string, string> = {
  traffic_total: "Tracks observados en el área externa",
  store_pass: "Tracks que pasan en el área externa",
  entries: "Cruces confirmados hacia el área interna",
  exits: "Cruces confirmados hacia afuera",
  entry_rate: "Entradas / pasos en el área externa",
  dwell_mean_seconds: "Tiempo medio observable en área externa",
  dwell_median_seconds: "Tiempo mediano observable en área externa",
  visible_occupancy: "Ocupación observable en el último frame analizado",
};

export const LABEL_TEXT: Record<string, string> = {
  visit_estimate: "estimación de visitas", visible: "visible", observable: "observable",
};

export const UNAVAILABLE_REASON: Record<string, string> = {
  no_passes: "Sin pasos en el área externa",
  no_closed_dwells: "Sin permanencias completas observadas",
  scene_element_missing: "Falta configurar la zona o línea necesaria",
  metrics_not_generated: "Todavía no se generaron las métricas",
};

const number = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 });
export function formatMetric(code: string, value: number): string {
  if (code === "entry_rate") return `${number.format(value * 100)} %`;
  if (code.endsWith("_seconds")) return `${number.format(value)} s`;
  return number.format(value);
}

export function formatVideoTime(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

export function peakCaption(startSeconds: number, trackCount: number, durationSeconds: number): string {
  if (durationSeconds > 0 && durationSeconds < 60) {
    return `No hay horario pico. El video dura menos de un minuto y en ese tramo se observaron ${trackCount} tracks.`;
  }
  return `Horario pico: ${formatVideoTime(startSeconds)}–${formatVideoTime(startSeconds + 60)}, ${trackCount} tracks observados`;
}

export const EVENT_NAME: Record<string, string> = {
  zone_enter: "Ingreso a zona", zone_exit: "Salida de zona", store_pass: "Paso en el área externa",
  store_enter: "Entrada a la zona", store_exit: "Salida de la zona", dwell: "Permanencia observable",
};
