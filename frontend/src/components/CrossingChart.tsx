import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { LiveMinute, LiveShopSnapshot } from "../api/liveMessages";

export function CrossingChart({ minutes, summary }: { minutes: LiveMinute[]; summary: LiveShopSnapshot }) {
  const access = summary.label_mode === "access";
  const entriesAreA = summary.entry_direction === "a_to_b";
  const data = minutes.map((minute) => ({ minute: `${minute.bucket_index} min`,
    first: access || entriesAreA ? minute.entries : minute.exits,
    second: access || entriesAreA ? minute.exits : minute.entries,
    coverage: minute.coverage_incomplete || minute.unknown_tail ? "Cobertura incompleta" :
      minute.is_open ? "Minuto en curso" : "Minuto cerrado" }));
  return <section aria-label="Cruces por minuto">
    <h2>Cruces por minuto</h2>
    {data.length === 0 ? <p>Todavía no hay minutos analizados.</p> : <>
      <div style={{ width: "100%", height: 240 }}><ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="minute" />
          <YAxis allowDecimals={false} /><Tooltip /><Legend />
          <Bar dataKey="first" name={access ? "Entradas" : "A → B"} fill="#2563eb" />
          <Bar dataKey="second" name={access ? "Salidas" : "B → A"} fill="#16a34a" />
        </BarChart>
      </ResponsiveContainer></div>
      <p>El minuto en curso puede cambiar al confirmarse un cruce. Los intervalos sin análisis no representan cero personas.</p>
      <details><summary>Ver datos y cobertura</summary><table><thead><tr><th>Minuto</th>
        <th>{access ? "Entradas" : "A → B"}</th><th>{access ? "Salidas" : "B → A"}</th><th>Cobertura</th>
      </tr></thead><tbody>{data.map((row) => <tr key={row.minute}><th>{row.minute}</th>
        <td>{row.first}</td><td>{row.second}</td><td>{row.coverage}</td></tr>)}</tbody></table></details>
    </>}
  </section>;
}
