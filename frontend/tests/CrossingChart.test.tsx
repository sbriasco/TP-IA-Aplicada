import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { CrossingChart } from "../src/components/CrossingChart";
import type { LiveMinute, LiveShopSnapshot } from "../src/api/liveMessages";

it("usa la hora de captura, conserva dirección y muestra huecos de cobertura", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const summary: LiveShopSnapshot = { shop_id: "one", shop_name: "Local", entry_count: 1,
    exit_count: 2, a_to_b_count: 2, b_to_a_count: 1, total_crossings: 3,
    label_mode: "directions", entry_direction: "b_to_a", partial: true };
  const minute: LiveMinute = { shop_id: "one", bucket_index: 0, start_seconds: 0,
    end_seconds: 60, entries: 1, exits: 2, observed_seconds: 60, missing_seconds: 0,
    pending_count: 0, is_open: false, coverage_incomplete: false, unknown_tail: false, revision: 1 };
  const container = document.createElement("div");
  document.body.append(container); const root = createRoot(container);
  try {
    await act(async () => root.render(<CrossingChart minutes={[minute,
      { ...minute, bucket_index: 1, start_seconds: 60, end_seconds: 120,
        observed_seconds: 0, missing_seconds: 60, coverage_incomplete: true }]}
      summary={summary} captureStartedAt="2026-10-05T17:21:00-03:00" />));
    const rows = container.querySelectorAll("tbody tr");
    expect(rows[0].textContent).toContain("17:21");
    expect(Array.from(rows[0].querySelectorAll("td")).slice(0, 2).map((cell) => cell.textContent)).toEqual(["2", "1"]);
    expect(rows[1].textContent).toContain("Sin datos");
  } finally { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals(); }
});
