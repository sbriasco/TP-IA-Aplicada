import { useState } from "react";

import { JobPreviewPage } from "./pages/JobPreviewPage";

export function App() {
  const initialJobId = new URLSearchParams(window.location.search).get("job") ?? "";
  const [jobId, setJobId] = useState(initialJobId);
  const [input, setInput] = useState(initialJobId);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = input.trim();
    if (normalized === "") return;
    window.history.replaceState(null, "", `?job=${encodeURIComponent(normalized)}`);
    setJobId(normalized);
  }

  if (jobId !== "") {
    return <JobPreviewPage jobId={jobId} />;
  }

  return (
    <main>
      <h1>Supervisión de FlowSight</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="job-id">Identificador del trabajo</label>
        <input
          id="job-id"
          name="job-id"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          required
        />
        <button type="submit">Supervisar</button>
      </form>
    </main>
  );
}
