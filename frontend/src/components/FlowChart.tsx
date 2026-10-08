import { useId } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FlowPoint } from "../flow/flowSeries";
import { formatVideoTime } from "../presentation/metrics";
import styles from "./FlowChart.module.css";

export function FlowChart({ points, fromSeconds, toSeconds, fit = false }: { fit?: boolean; points: FlowPoint[]; fromSeconds: number; toSeconds: number }) {
  const gradientId = `flow-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  if (points.length === 0) return <p className={styles.empty}>No hay tracks en el área externa para este tramo.</p>;
  const step = Math.max(1, Math.ceil((toSeconds - fromSeconds) / 4));
  const ticks = [fromSeconds, ...[1, 2, 3].map(index => fromSeconds + step * index).filter(seconds => seconds < toSeconds), toSeconds];
  return <div className={`${styles.chart}${fit ? ` ${styles.fit}` : ""}`} role="img" aria-label="Flujo temporal de tracks en el área externa">
    <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 640, height: 260 }}>
      <AreaChart data={points} margin={{ top: 12, right: 16, bottom: 8, left: 0 }} accessibilityLayer>
        <defs><linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#14b8a6" stopOpacity={0.25} /><stop offset="100%" stopColor="#14b8a6" stopOpacity={0} /></linearGradient></defs>
        <CartesianGrid stroke="var(--fs-line)" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="seconds" type="number" domain={[fromSeconds, toSeconds]} ticks={ticks} tickFormatter={formatVideoTime}
          tick={{ fontSize: 11, fill: "var(--fs-muted)" }} axisLine={false} tickLine={false} minTickGap={12} tickMargin={10} />
        <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--fs-muted)" }} axisLine={false} tickLine={false} width={30} />
        <Tooltip labelFormatter={value => `${formatVideoTime(Number(value))} · ${Number(value)} s`}
          formatter={value => [String(value), "Tracks en el área externa"]}
          contentStyle={{ background: "var(--fs-surface)", border: "1px solid var(--fs-line)", borderRadius: 8, padding: "8px 12px", color: "var(--fs-ink)", fontSize: 12, boxShadow: "0 4px 16px rgb(0 0 0 / 18%)" }}
          labelStyle={{ color: "var(--fs-muted)", marginBottom: 4 }} itemStyle={{ color: "var(--fs-ink)", padding: 0 }} />
        <Area type="stepAfter" dataKey="track_count" name="Tracks en el área externa" stroke="#14b8a6" strokeWidth={2}
          fill={`url(#${gradientId})`} dot={false} activeDot={{ r: 4, stroke: "var(--fs-surface)", strokeWidth: 2 }} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  </div>;
}
