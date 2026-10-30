import { useEffect, useRef, useState, type FormEvent } from "react";
import { Bot, PanelLeft, PanelLeftClose, SquarePen } from "lucide-react";
import {
  getChatThread,
  listChatThreads,
  postChat,
  type ChatResponse,
  type ChatThreadSummary,
} from "../api/chat";
import { ApiRequestError } from "../api/http";
import { AgentAnswer } from "./AgentAnswer";
import styles from "./SessionChatPanel.module.css";

interface SessionChatPanelProps {
  apiBaseUrl: string;
  sessionId: string;
  shopId: string | null;
  shopName?: string;
}
interface Turn {
  id: number;
  question: string;
  answer: ChatResponse | null;
}

const SUGGESTIONS = [
  "¿Cuántos ingresos hubo?",
  "¿Cuál fue la tasa de ingreso?",
  "¿Hubo posible compra estimada?",
  "Compará el tráfico con la última",
];

export function SessionChatPanel({ apiBaseUrl, sessionId, shopId, shopName }: SessionChatPanelProps) {
  const [question, setQuestion] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [threads, setThreads] = useState<ChatThreadSummary[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const generation = useRef(0);
  const nextId = useRef(0);
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    generation.current++;
    setTurns([]);
    setQuestion("");
    setWaiting(false);
    setThreadId(null);
    const scope = generation.current;
    setLoadingThreads(true);
    void listChatThreads(apiBaseUrl, sessionId)
      .then((rows) => {
        if (generation.current !== scope) return;
        setThreads(rows);
      })
      .catch(() => {
        if (generation.current === scope) setThreads([]);
      })
      .finally(() => {
        if (generation.current === scope) setLoadingThreads(false);
      });
    return () => {
      generation.current++;
    };
  }, [apiBaseUrl, sessionId, shopId]);

  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [turns, waiting]);

  async function openThread(id: string) {
    const scope = generation.current;
    setWaiting(true);
    try {
      const detail = await getChatThread(apiBaseUrl, id);
      if (generation.current !== scope) return;
      if (shopId !== null && detail.thread.shop_id !== null && detail.thread.shop_id !== shopId) {
        setThreadId(null);
        setTurns([]);
        return;
      }
      const restored: Turn[] = [];
      for (let index = 0; index < detail.messages.length; index += 1) {
        const message = detail.messages[index];
        if (message.role !== "user") continue;
        const next = detail.messages[index + 1];
        restored.push({
          id: ++nextId.current,
          question: message.content,
          answer:
            next?.role === "assistant"
              ? next.answer ?? {
                  status: "answered",
                  message: next.content,
                  session_id: sessionId,
                  shop_id: shopId,
                  shop_name: shopName ?? null,
                  scope: null,
                  figures: [],
                  model_calls: 0,
                  thread_id: id,
                }
              : null,
        });
      }
      setThreadId(id);
      setTurns(restored);
    } catch {
      if (generation.current === scope) {
        setThreadId(null);
        setTurns([]);
      }
    } finally {
      if (generation.current === scope) setWaiting(false);
    }
  }

  function startNewConversation() {
    setThreadId(null);
    setTurns([]);
    setQuestion("");
    input.current?.focus();
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = String(new FormData(event.currentTarget).get("question") ?? "").trim();
    if (!text || waiting || shopId === null) return;
    const scope = generation.current;
    const id = ++nextId.current;
    const activeThread = threadId;
    setTurns((current) => [...current.slice(-19), { id, question: text, answer: null }]);
    setQuestion("");
    setWaiting(true);
    void postChat(apiBaseUrl, text, sessionId, shopId, activeThread)
      .then((answer) => {
        if (generation.current !== scope) return;
        if (answer.thread_id) setThreadId(answer.thread_id);
        setTurns((current) =>
          current.map((turn) => (turn.id === id ? { ...turn, answer } : turn)),
        );
        void listChatThreads(apiBaseUrl, sessionId).then((rows) => {
          if (generation.current === scope) setThreads(rows);
        });
      })
      .catch((reason: unknown) => {
        if (generation.current !== scope) return;
        const answer: ChatResponse = {
          status: "error",
          message:
            reason instanceof ApiRequestError
              ? reason.error.message
              : "No se pudo consultar al agente.",
          session_id: sessionId,
          shop_id: shopId,
          shop_name: null,
          scope: null,
          figures: [],
          model_calls: 0,
          thread_id: activeThread,
        };
        setTurns((current) =>
          current.map((turn) => (turn.id === id ? { ...turn, answer } : turn)),
        );
      })
      .finally(() => {
        if (generation.current === scope) setWaiting(false);
      });
  }

  return (
    <aside className={styles.panel} aria-label="Chat de la sesión">
      <header className={styles.heading}>
        <span className={styles.avatar} aria-hidden="true">
          <Bot size={23} />
        </span>
        <div>
          <h2>Agente FlowSight</h2>
          <p>Consultas sobre este análisis</p>
        </div>
      </header>
      <div className={styles.context}>
        {shopName ?? "Zona seleccionada"}
        <span> · Toda la sesión</span>
      </div>
      <div className={styles.body}>
        {historyOpen ? (
          <nav
            id="session-chat-history"
            className={styles.history}
            aria-label="Conversaciones de esta sesión"
          >
            <div className={styles.historyHeading}>
              <span>Historial</span>
              <div className={styles.historyActions}>
                <button type="button" onClick={startNewConversation}>
                  Nueva
                </button>
                <button
                  type="button"
                  className={styles.iconButton}
                  aria-label="Ocultar historial"
                  aria-expanded={true}
                  aria-controls="session-chat-history"
                  onClick={() => setHistoryOpen(false)}
                >
                  <PanelLeftClose size={16} aria-hidden="true" />
                </button>
              </div>
            </div>
            {loadingThreads && <p className={styles.historyEmpty}>Cargando…</p>}
            {!loadingThreads && threads.length === 0 && (
              <p className={styles.historyEmpty}>Todavía no hay conversaciones.</p>
            )}
            <ul>
              {threads.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className={row.id === threadId ? styles.historyActive : undefined}
                    disabled={
                      waiting ||
                      (shopId !== null && row.shop_id !== null && row.shop_id !== shopId)
                    }
                    onClick={() => {
                      void openThread(row.id);
                    }}
                  >
                    {row.title}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        ) : null}
        <div className={styles.main}>
          <div className={styles.toolbar}>
            {!historyOpen ? (
              <button
                type="button"
                className={styles.toolbarButton}
                aria-expanded={false}
                aria-controls="session-chat-history"
                onClick={() => setHistoryOpen(true)}
              >
                <PanelLeft size={16} aria-hidden="true" />
                Historial
              </button>
            ) : null}
            <button
              type="button"
              className={styles.toolbarButton}
              onClick={startNewConversation}
            >
              <SquarePen size={16} aria-hidden="true" />
              Nueva conversación
            </button>
          </div>
          <div
            className={styles.conversation}
            role="log"
            aria-label="Conversación con el agente"
            ref={log}
            aria-busy={waiting}
          >
            {turns.length === 0 && (
              <div className={styles.welcome}>
                <span className={styles.author}>Agente FlowSight</span>
                <p>
                  Hola, puedo citar métricas guardadas de esta zona y contrastar con otras sesiones.
                  Los seguimientos usan el hilo abierto.
                </p>
                <p className={styles.hint}>
                  Cada pregunta usa la zona seleccionada. Elegí un hilo del historial o empezá uno nuevo.
                </p>
                <div className={styles.suggestions}>
                  {SUGGESTIONS.map((text) => (
                    <button
                      type="button"
                      key={text}
                      disabled={shopId === null}
                      onClick={() => {
                        setQuestion(text);
                        input.current?.focus();
                      }}
                    >
                      {text}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {turns.map((turn) => (
              <div className={styles.turn} key={turn.id}>
                <div className={styles.question}>
                  <span className={styles.author}>Vos</span>
                  <p>{turn.question}</p>
                </div>
                {turn.answer && <AgentAnswer answer={turn.answer} />}
              </div>
            ))}
            {waiting && (
              <p className={styles.waiting} role="status">
                <span aria-hidden="true">•••</span> Consultando tus métricas…
              </p>
            )}
          </div>
        </div>
      </div>
      <form onSubmit={onSubmit} className={styles.composer}>
        <label htmlFor="agent-question">Pregunta al agente</label>
        <div>
          <input
            ref={input}
            id="agent-question"
            name="question"
            placeholder="Preguntá sobre este análisis…"
            value={question}
            maxLength={2000}
            disabled={shopId === null}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <button type="submit" disabled={waiting || shopId === null || !question.trim()}>
            Enviar
          </button>
        </div>
        <small>Responde con métricas registradas. El historial orienta el seguimiento; las cifras salen de lecturas del turno.</small>
      </form>
    </aside>
  );
}
