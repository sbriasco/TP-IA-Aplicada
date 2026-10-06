import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import styles from "./Modal.module.css";

interface ModalProps {
  title: string;
  onClose: () => void;
  busy?: boolean;
  children: ReactNode;
  subtitle?: string;
  wide?: boolean;
}

export function Modal({ title, onClose, busy = false, children, subtitle, wide = false }: ModalProps) {
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
    <dialog ref={dialog} className={`${styles.dialog}${wide ? " " + styles.wide : ""}`} aria-label={title} onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
      <div className={styles.heading}><div><h2>{title}</h2>{subtitle && <p className={styles.subtitle}>{subtitle}</p>}</div><button type="button" aria-label="Cerrar" disabled={busy} onClick={onClose}><X size={19} aria-hidden="true" /></button></div>
      {children}
    </dialog>
  );
}
