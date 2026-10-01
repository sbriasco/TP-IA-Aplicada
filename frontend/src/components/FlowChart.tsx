import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TrafficBucket } from "../api/metrics";
import { formatVideoTime } from "../presentation/metrics";
import styles from "./FlowChart.module.css";

export function FlowChart({ buckets }: { buckets: TrafficBucket[] }) {
  if (buckets.length === 0) return <p className={styles.empty}>No hay intervalos de flujo para este tramo.</p>;
  return (
    <div className={styles.chart}>
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 480, height: 240 }}>
        <BarChart data={buckets} margin={{ top: 10, right: 12, bottom: 8, left: -20 }} accessibilityLayer>
          <CartesianGrid stroke="#e5ecef" vertical={false} />
          <XAxis dataKey="start_seconds" tickFormatter={formatVideoTime} tick={{ fontSize: 11, fill: "#637480" }} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#637480" }} axisLine={false} tickLine={false} />
          <Tooltip labelFormatter={(value) => `Desde ${formatVideoTime(Number(value))} del video`} cursor={{ fill: "#edf5f6" }} />
          <Bar dataKey="track_count" name="Tracks observados" fill="#146071" radius={[4, 4, 0, 0]} maxBarSize={48} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
