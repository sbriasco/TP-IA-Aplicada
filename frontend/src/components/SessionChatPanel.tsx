import { useState, type FormEvent } from "react";

import { postChat, type ChatFigure, type ChatResponse } from "../api/chat";
import { ApiRequestError } from "../api/http";

import styles from "./SessionChatPanel.module.css";

const FIGURE_LABEL: Record<string, string> = {
  visit_estimate: "estimación de visitas",
  visible: "visible",
  observable: "observable",
};

interface SessionChatPanelProps {
  apiBaseUrl: string;
  sessionId: string;
  shopId: string | null;
}

export function SessionChatPanel({ apiBaseUrl, sessionId, shopId }: SessionChatPanelProps) {
  const [question, setQuestion] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [answer, setAnswer] = useState<ChatResponse | null>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = String(new FormData(event.currentTarget).get("question") ?? "").trim();
    if (text === "" || waiting) return;
    setWaiting(true);
    setAnswer(null);
    void postChat(apiBaseUrl, text, sessionId, shopId)
      .then((response) => {
        setAnswer(response);
      })
      .catch((reason: unknown) => {
        const message =
          reason instanceof ApiRequestError ? reason.error.message : "No se pudo consultar el chat.";
        setAnswer({
          status: "error",
          message,
          session_id: sessionId,
          shop_id: shopId,
          shop_name: null,
          scope: null,
          figures: [],
          model_calls: 0,
        });
      })
      .finally(() => {
        setWaiting(false);
      });
  }

  return (
    <section className={styles.panel} aria-label="Chat de la sesión">
      <form onSubmit={onSubmit}>
        <label>
          Pregunta
          <input
            name="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </label>
        <button type="submit">Enviar</button>
      </form>
      {waiting && <p className={styles.waiting}>Consultando</p>}
      {answer !== null && !waiting && (
        <section aria-label="Respuesta">
          <p>{answer.message}</p>
          {answer.status === "answered" && (
            <>
              {answer.shop_name !== null && <p>{answer.shop_name}</p>}
              <p>toda la sesión</p>
              <ul>
                {answer.figures.map((figure) => (
                  <li key={figure.code}>
                    <FigureText figure={figure} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </section>
  );
}

function FigureText({ figure }: { figure: ChatFigure }) {
  if (figure.code === "peak") {
    return <>{figure.start_seconds} s</>;
  }
  const label = FIGURE_LABEL[figure.label];
  const value =
    figure.availability === "available" && figure.value !== null ? figure.value : "no disponible";
  return (
    <>
      {value}
      {label !== undefined ? ` ${label}` : ""}
    </>
  );
}
