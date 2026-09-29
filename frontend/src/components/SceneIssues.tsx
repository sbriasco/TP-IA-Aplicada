import { useId, type Dispatch } from "react";

import type { EditorAction, EditorElement, EditorState } from "../editor/editorState";
import { issueElementTitle, shopDisplayName } from "../editor/labels";
import type { SceneIssue } from "../types/scene";

interface SceneIssuesProps {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
}

function editorElement(issue: SceneIssue): EditorElement | null {
  return issue.element === "version" || issue.element === "shop" ? null : issue.element;
}

/** Errores del último 422 y advertencias del último guardado; cada uno lleva a su elemento (T043). */
export function SceneIssues({ state, dispatch }: SceneIssuesProps) {
  const id = useId();

  function describe(issue: SceneIssue): string {
    if (issue.shop_index === null) return `${issueElementTitle(issue.element)}: ${issue.message}`;
    const shop = state.shops[issue.shop_index];
    const name = issue.shop_name ?? shopDisplayName(shop?.name ?? "", issue.shop_index);
    const where = issue.element === "shop" ? name : `${name} · ${issueElementTitle(issue.element)}`;
    return `${where}: ${issue.message}`;
  }

  function list(items: SceneIssue[]) {
    return (
      <ul>
        {items.map((issue, index) => {
          const shopIndex = issue.shop_index;
          const text = describe(issue);
          return (
            <li key={`${issue.rule}-${issue.element}-${shopIndex ?? "v"}-${index}`}>
              {shopIndex === null || state.shops[shopIndex] === undefined ? (
                text
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    dispatch({
                      type: "select",
                      selection: { shopIndex, element: editorElement(issue), vertexIndex: null },
                    })
                  }
                >
                  {text}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    );
  }

  if (state.issues.length === 0 && state.warnings.length === 0) return null;

  return (
    <>
      {state.issues.length > 0 && (
        <section aria-labelledby={`${id}-errors`}>
          <h2 id={`${id}-errors`}>Errores</h2>
          {list(state.issues)}
        </section>
      )}
      {state.warnings.length > 0 && (
        <section aria-labelledby={`${id}-warnings`}>
          <h2 id={`${id}-warnings`}>Advertencias</h2>
          {list(state.warnings)}
        </section>
      )}
    </>
  );
}
