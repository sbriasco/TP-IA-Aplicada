import { useEffect, useRef, type ReactNode } from "react";
import styles from "./Modal.module.css";

interface ModalProps {
  title: string;
  onClose: () => void;
  busy?: boolean;
  children: ReactNode;
}

export function Modal({ title, onClose, busy = false, children }: ModalProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previousFocus = document.activeElement;
    const element = dialog.current;
    if (element && !element.open) {
      if (typeof element.showModal === "function") element.showModal();
      else element.setAttribute("open", "");
    }
    return () => { if (previousFocus instanceof HTMLElement) previousFocus.focus(); };
  }, []);
  return (
    <dialog ref={dialog} className={styles.dialog} aria-label={title} onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
      <div className={styles.heading}><h2>{title}</h2><button type="button" aria-label="Cerrar" disabled={busy} onClick={onClose}>×</button></div>
      {children}
    </dialog>
  );
}
