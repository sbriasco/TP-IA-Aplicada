import { useId, type Dispatch } from "react";

import type { EditorAction, EditorState } from "../editor/editorState";
import { shopDisplayName } from "../editor/labels";
import type { EntryDirection } from "../types/scene";

interface EntryLineControlsProps {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
}

const OPTIONS: { value: EntryDirection; label: string }[] = [
  { value: "a_to_b", label: "A → B es entrada" },
  { value: "b_to_a", label: "B → A es entrada" },
];

/** Sentido de entrada de la línea del local seleccionado (T043, FR-032). */
export function EntryLineControls({ state, dispatch }: EntryLineControlsProps) {
  const id = useId();
  const shopIndex = state.selection?.shopIndex ?? null;
  const shop = shopIndex === null ? undefined : state.shops[shopIndex];
  if (shop === undefined || shopIndex === null) return null;

  const name = shopDisplayName(shop.name, shopIndex);
  const line = shop.entry_line;

  return (
    <fieldset disabled={line === null}>
      <legend>Sentido de entrada de {name}</legend>
      {line === null && <p>{name} todavía no tiene línea de entrada.</p>}
      {OPTIONS.map((option) => (
        <p key={option.value}>
          <input
            id={`${id}-${option.value}`}
            type="radio"
            name={`${id}-direction`}
            value={option.value}
            checked={line?.entry_direction === option.value}
            onChange={() => dispatch({ type: "setEntryDirection", shopIndex, direction: option.value })}
          />{" "}
          <label htmlFor={`${id}-${option.value}`}>{option.label}</label>
        </p>
      ))}
      <p>
        <small>
          A y B son los lados de la línea que se ven sobre el frame; la flecha marca el sentido que cuenta
          como entrada.
        </small>
      </p>
    </fieldset>
  );
}
