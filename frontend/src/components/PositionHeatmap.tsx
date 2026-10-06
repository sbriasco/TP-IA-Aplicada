import styles from "./PositionHeatmap.module.css";

interface PositionHeatmapProps {
  availability: "available" | "unavailable";
  samples: { foot: [number, number] }[];
}

export function PositionHeatmap({ availability, samples }: PositionHeatmapProps) {
  if (availability === "unavailable" || samples.length === 0) {
    return <p>No hay muestra de posiciones en este equipo.</p>;
  }
  return (
    <svg className={styles.overlay} viewBox="0 0 1 1" preserveAspectRatio="none" role="img" aria-label="Mapa de calor">
      {samples.map((sample, index) => (
        <circle
          key={`${sample.foot[0]}-${sample.foot[1]}-${index}`}
          className={styles.point}
          cx={sample.foot[0]}
          cy={sample.foot[1]}
          r={0.015}
        />
      ))}
    </svg>
  );
}
