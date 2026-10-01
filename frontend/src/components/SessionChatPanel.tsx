import { useEffect, useRef, useState, type FormEvent } from "react";
import { postChat, type ChatResponse } from "../api/chat";
import { ApiRequestError } from "../api/http";
import { AgentAnswer } from "./AgentAnswer";
import styles from "./SessionChatPanel.module.css";

interface SessionChatPanelProps {
  apiBaseUrl: string;
  sessionId: string;
  shopId: string | null;
  shopName?: string;
}
interface Turn { id: number; question: string; answer: ChatResponse | null; }
const SUGGESTIONS = ["¿Cuántos ingresos hubo?", "¿Cuál fue el horario pico?", "¿Cuál fue la permanencia media?"];

export function SessionChatPanel({ apiBaseUrl, sessionId, shopId, shopName }: SessionChatPanelProps) {
  const [question, setQuestion] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const generation = useRef(0);
  const nextId = useRef(0);
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    generation.current++;
    setTurns([]);
    setQuestion("");
    setWaiting(false);
    return () => { generation.current++; };
  }, [apiBaseUrl, sessionId, shopId]);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [turns, waiting]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = String(new FormData(event.currentTarget).get("question") ?? "").trim();
    if (!text || waiting || shopId === null) return;
    const scope = generation.current;
    const id = ++nextId.current;
    setTurns((current) => [...current.slice(-19), { id, question: text, answer: null }]);
    setQuestion("");
    setWaiting(true);
    void postChat(apiBaseUrl, text, sessionId, shopId)
      .then((answer) => {
        if (generation.current === scope) setTurns((current) => current.map((turn) => turn.id === id ? { ...turn, answer } : turn));
      })
      .catch((reason: unknown) => {
        if (generation.current !== scope) return;
        const answer: ChatResponse = {
          status: "error", message: reason instanceof ApiRequestError ? reason.error.message : "No se pudo consultar al agente.",
          session_id: sessionId, shop_id: shopId, shop_name: null, scope: null, figures: [], model_calls: 0,
        };
        setTurns((current) => current.map((turn) => turn.id === id ? { ...turn, answer } : turn));
      })
      .finally(() => { if (generation.current === scope) setWaiting(false); });
  }

  return (
    <aside className={styles.panel} aria-label="Chat de la sesión">
      <header className={styles.heading}>
        <span className={styles.avatar} aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 5h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-8l-5 3v-3H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" fill="none" stroke="currentColor" strokeWidth="1.6"/><circle cx="8" cy="11" r="1"/><circle cx="12" cy="11" r="1"/><circle cx="16" cy="11" r="1"/></svg></span>
        <div><h2>Agente FlowSight</h2><p>Asistente de IA · tus resultados</p></div>
      </header>
      <div className={styles.context}>{shopName ?? "Local seleccionado"}<span> · Toda la sesión</span></div>
      <div className={styles.conversation} role="log" aria-label="Conversación con el agente" ref={log} aria-busy={waiting}>
        {turns.length === 0 && <div className={styles.welcome}>
          <span className={styles.author}>Agente FlowSight</span>
          <p>Hola, puedo ayudarte a interpretar el tráfico, los ingresos y la permanencia de este análisis.</p>
          <p className={styles.hint}>Cada pregunta consulta el local seleccionado. Incluí lo que querés comparar o medir.</p>
          <div className={styles.suggestions}>{SUGGESTIONS.map((text) => <button type="button" key={text} disabled={shopId === null} onClick={() => { setQuestion(text); input.current?.focus(); }}>{text}</button>)}</div>
        </div>}
        {turns.map((turn) => <div className={styles.turn} key={turn.id}>
          <div className={styles.question}><span className={styles.author}>Vos</span><p>{turn.question}</p></div>
          {turn.answer && <AgentAnswer answer={turn.answer} />}
        </div>)}
        {waiting && <p className={styles.waiting} role="status"><span aria-hidden="true">•••</span> Consultando tus métricas…</p>}
      </div>
      <form onSubmit={onSubmit} className={styles.composer}>
        <label htmlFor="agent-question">Pregunta al agente</label>
        <div><input ref={input} id="agent-question" name="question" placeholder="Preguntá sobre este análisis…" value={question} maxLength={2000} disabled={shopId === null} onChange={(event) => setQuestion(event.target.value)} /><button type="submit" disabled={waiting || shopId === null || !question.trim()}>Enviar</button></div>
        <small>Responde con métricas registradas. Las estimaciones conservan su alcance.</small>
      </form>
    </aside>
  );
}
