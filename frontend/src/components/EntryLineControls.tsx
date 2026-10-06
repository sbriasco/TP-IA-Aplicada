import { useId, type Dispatch } from "react";

import type { EditorAction, EditorState } from "../editor/editorState";
import { shopDisplayName } from "../editor/labels";
import type { EntryDirection } from "../types/scene";

interface EntryLineControlsProps {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
  compact?: boolean;
}

const OPTIONS: { value: EntryDirection; label: string }[] = [
  { value: "a_to_b", label: "A → B es entrada" },
  { value: "b_to_a", label: "B → A es entrada" },
];

/** Sentido de entrada de la línea dla zona seleccionada (T043, FR-032). */
export function EntryLineControls({ state, dispatch, compact = false }: EntryLineControlsProps) {
  const id = useId();
  const shopIndex = state.selection?.shopIndex ?? null;
  const shop = shopIndex === null ? undefined : state.shops[shopIndex];
  if (shop === undefined || shopIndex === null) return null;

  const name = shopDisplayName(shop.name, shopIndex);
  const line = shop.entry_line;

  if (compact) return <fieldset disabled={line === null} className="!m-0 !p-2 !rounded-lg border-[var(--fs-line)]"><legend className="!text-xs">Sentido de entrada</legend><div className="flex gap-2">{OPTIONS.map(option => <button key={option.value} type="button" className="flex-1 !min-h-8 !py-2 !text-xs" aria-label={option.label} aria-pressed={line?.entry_direction === option.value} onClick={() => dispatch({ type: "setEntryDirection", shopIndex, direction: option.value })}>{option.value === "a_to_b" ? "A → B" : "B → A"}</button>)}</div></fieldset>;

  return (
    <fieldset disabled={line === null} className="!m-0 !p-3 !rounded-lg border-[var(--fs-line)]">
      <legend className="!text-xs">Sentido de entrada de {name}</legend>
      {line === null && <p>{name} todavía no tiene línea de entrada.</p>}
      <div className="flex flex-wrap gap-2">{OPTIONS.map((option) => (
        <label htmlFor={`${id}-${option.value}`} key={option.value} className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-2 py-3 text-xs cursor-pointer ${line?.entry_direction === option.value ? "border-[var(--fs-accent)] bg-[var(--fs-tint)] text-[var(--fs-accent)]" : "border-[var(--fs-line)]"}`}>
          <input
            id={`${id}-${option.value}`}
            type="radio"
            name={`${id}-direction`}
            value={option.value}
            checked={line?.entry_direction === option.value}
            onChange={() => dispatch({ type: "setEntryDirection", shopIndex, direction: option.value })}
          />
          {option.label}
        </label>
      ))}</div>
      <p>
        <small>
          A y B son los lados de la línea que se ven sobre el frame; la flecha marca el sentido que cuenta
          como entrada.
        </small>
      </p>
    </fieldset>
  );
}
