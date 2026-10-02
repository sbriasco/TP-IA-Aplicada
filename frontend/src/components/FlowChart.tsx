import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FlowPoint } from "../flow/flowSeries";
import { formatVideoTime } from "../presentation/metrics";
import styles from "./FlowChart.module.css";

export function FlowChart({ points, fromSeconds, toSeconds }: { points: FlowPoint[]; fromSeconds: number; toSeconds: number }) {
  if (points.length === 0) return <p className={styles.empty}>No hay tracks en la zona frontal para este tramo.</p>;
  return (
    <div className={styles.chart}>
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 480, height: 240 }}>
        <LineChart data={points} margin={{ top: 10, right: 12, bottom: 8, left: -12 }} accessibilityLayer>
          <CartesianGrid stroke="#e5ecef" vertical={false} />
          <XAxis
            dataKey="seconds"
            type="number"
            domain={[fromSeconds, toSeconds]}
            tickFormatter={formatVideoTime}
            tick={{ fontSize: 11, fill: "#637480" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#637480" }} axisLine={false} tickLine={false} width={28} />
          <Tooltip
            labelFormatter={(value) => formatVideoTime(Number(value))}
            formatter={(value) => [String(value), "En la zona frontal"]}
          />
          <Line
            type="stepAfter"
            dataKey="track_count"
            name="Tracks en la zona frontal"
            stroke="#146071"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
