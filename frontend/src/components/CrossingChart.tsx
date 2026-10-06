import { Line, LineChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { LiveMinute, LiveShopSnapshot } from "../api/liveMessages";

export function CrossingChart({ minutes, summary, captureStartedAt }: {
  minutes: LiveMinute[]; summary: LiveShopSnapshot; captureStartedAt?: string | null;
}) {
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
    <h2>Cruces por minuto</h2>
    {data.length === 0 ? <p>Todavía no hay minutos analizados.</p> : <>
      <div style={{ width: "100%", height: 240 }}><ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="timestamp" type="number" domain={["dataMin", "dataMax"]}
          ticks={data.map((row) => row.timestamp)} minTickGap={24}
          tickFormatter={(value: number) => Number.isFinite(start) ? new Date(value).toLocaleTimeString("es-AR", {
            hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "America/Argentina/Buenos_Aires" }) : "—"} />
          <YAxis allowDecimals={false} /><Tooltip labelFormatter={(value) => Number.isFinite(start) ?
            new Date(Number(value)).toLocaleString("es-AR", { hourCycle: "h23", timeZone: "America/Argentina/Buenos_Aires" }) : "Hora no disponible"} /><Legend />
          <Line type="linear" dataKey="first" name={access ? "Entradas" : "A → B"} stroke="#2563eb" connectNulls={false} isAnimationActive={false} />
          <Line type="linear" dataKey="second" name={access ? "Salidas" : "B → A"} stroke="#16a34a" connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer></div>
      <p>El minuto en curso puede cambiar al confirmarse un cruce. Los intervalos sin análisis no representan cero personas.</p>
      <details><summary>Ver datos y cobertura</summary><table><thead><tr><th>Minuto</th>
        <th>{access ? "Entradas" : "A → B"}</th><th>{access ? "Salidas" : "B → A"}</th><th>Cobertura</th>
      </tr></thead><tbody>{data.map((row) => <tr key={row.timestamp}><th>{row.minute}</th>
        <td>{row.first ?? "Sin datos"}</td><td>{row.second ?? "Sin datos"}</td><td>{row.coverage}</td></tr>)}</tbody></table></details>
    </>}
  </section>;
}
