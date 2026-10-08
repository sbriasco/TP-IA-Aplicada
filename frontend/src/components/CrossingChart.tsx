import { Line, LineChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { LiveMinute, LiveShopSnapshot } from "../api/liveMessages";

export function CrossingChart({ minutes, summary, captureStartedAt, compact = false, report = false }: {
  minutes: LiveMinute[]; summary: LiveShopSnapshot; captureStartedAt?: string | null; compact?: boolean; report?: boolean;
}) {
  const styled = compact || report;
  const access = summary.label_mode === "access";
  const entriesAreA = summary.entry_direction === "a_to_b";
  const start = captureStartedAt ? Date.parse(captureStartedAt) : NaN;
  const data = minutes.map((minute) => ({ minute: Number.isFinite(start) ?
    new Date(start + minute.start_seconds * 1000).toLocaleTimeString("es-AR", {
      hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "America/Argentina/Buenos_Aires" }) : "Hora no disponible",
    timestamp: Number.isFinite(start) ? start + minute.start_seconds * 1000 : minute.start_seconds * 1000,
    first: minute.observed_seconds === 0 ? null : access || entriesAreA ? minute.entries : minute.exits,
    second: minute.observed_seconds === 0 ? null : access || entriesAreA ? minute.exits : minute.entries,
    coverage: minute.coverage_incomplete || minute.unknown_tail ? "Cobertura incompleta" :
      minute.is_open ? "Minuto en curso" : "Minuto cerrado" }));
  return <section aria-label="Cruces por minuto">
    {!report && <h2>Cruces por minuto</h2>}
    {data.length === 0 ? <div style={report ? { height: 220, display: "grid", placeItems: "center", color: "var(--fs-muted)" } : undefined}>Todavía no hay minutos analizados.</div> : <>
      <div style={{ width: "100%", height: report ? 220 : compact ? "var(--live-chart-height, 176px)" : 240 }}><ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={report ? { top: 8, right: 12, bottom: 0, left: 0 } : undefined}><CartesianGrid stroke={styled ? "var(--fs-line)" : undefined} strokeDasharray="3 3" /><XAxis tick={{ fill: styled ? "var(--fs-muted)" : undefined, fontSize: 11 }} dataKey="timestamp" type="number" domain={["dataMin", "dataMax"]}
          ticks={data.map((row) => row.timestamp)} minTickGap={24} axisLine={report ? false : undefined} tickLine={report ? false : undefined}
          tickFormatter={(value: number) => Number.isFinite(start) ? new Date(value).toLocaleTimeString("es-AR", {
            hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "America/Argentina/Buenos_Aires" }) : "—"} />
          <YAxis width={30} tick={{ fill: styled ? "var(--fs-muted)" : undefined, fontSize: 11 }} allowDecimals={false} axisLine={report ? false : undefined} tickLine={report ? false : undefined} /><Tooltip cursor={report ? { stroke: "var(--fs-muted)", strokeDasharray: "3 3" } : undefined} contentStyle={styled ? { background: "var(--fs-surface)", border: "1px solid var(--fs-line)", color: "var(--fs-ink)", fontSize: 12, borderRadius: 8 } : undefined} labelFormatter={(value) => Number.isFinite(start) ?
            new Date(Number(value)).toLocaleString("es-AR", { hourCycle: "h23", timeZone: "America/Argentina/Buenos_Aires" }) : "Hora no disponible"} /><Legend />
          <Line type="linear" dataKey="first" name={access ? "Entradas" : "A → B"} stroke={styled ? "var(--fs-accent)" : "#2563eb"} strokeWidth={report ? 2 : 1} connectNulls={false} isAnimationActive={false} />
          <Line type="linear" dataKey="second" name={access ? "Salidas" : "B → A"} stroke={report ? "var(--fs-muted)" : compact ? "#60a5fa" : "#16a34a"} strokeWidth={report ? 2 : 1} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer></div>
      {!compact && !report && <p>El minuto en curso puede cambiar al confirmarse un cruce. Los intervalos sin análisis no representan cero personas.</p>}
      {!report && <details><summary>Ver datos y cobertura</summary>{compact && <p>El minuto en curso puede cambiar al confirmarse un cruce. Los intervalos sin análisis no representan cero personas.</p>}<table><thead><tr><th>Minuto</th>
        <th>{access ? "Entradas" : "A → B"}</th><th>{access ? "Salidas" : "B → A"}</th><th>Cobertura</th>
      </tr></thead><tbody>{data.map((row) => <tr key={row.timestamp}><th>{row.minute}</th>
        <td>{row.first ?? "Sin datos"}</td><td>{row.second ?? "Sin datos"}</td><td>{row.coverage}</td></tr>)}</tbody></table></details>}
    </>}
  </section>;
}
