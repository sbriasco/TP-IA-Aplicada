import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, Layers } from "lucide-react";
import { configurationLabel } from "../presentation/configurationLabel";
import type { SceneVersionSummary } from "../types/scene";
import styles from "./SceneConfigurationSelect.module.css";

interface SceneConfigurationSelectProps {
  id: string;
  versions: SceneVersionSummary[];
  value: string;
  disabled: boolean;
  onChange: (id: string) => void;
}

export function SceneConfigurationSelect({ id, versions, value, disabled, onChange }: SceneConfigurationSelectProps) {
  const listId = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [placement, setPlacement] = useState<{ left: number; top: number; width: number; maxHeight: number } | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const selected = versions.find(version => version.id === value);
  const selectedIndex = Math.max(0, versions.findIndex(version => version.id === value));
  const open = placement !== null && !disabled;

  function positionMenu() {
    const rect = trigger.current?.getBoundingClientRect();
    if (!rect || disabled) return;
    const below = window.innerHeight - rect.bottom - 16;
    const above = rect.top - 16;
    const flip = below < 180 && above > below;
    const height = Math.max(60, Math.min(300, flip ? above : below));
    const menuHeight = Math.min(height, versions.length * 62 + 14);
    const width = Math.min(rect.width, window.innerWidth - 24);
    setPlacement({ left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)), top: flip ? rect.top - menuHeight - 6 : rect.bottom + 6, width, maxHeight: height });
  }

  function openMenu() {
    setActiveIndex(selectedIndex);
    positionMenu();
  }

  useEffect(() => {
    if (!open) return;
    function dismiss(event: PointerEvent) {
      if (event.target instanceof Node && !trigger.current?.contains(event.target) && !menu.current?.contains(event.target)) setPlacement(null);
    }
    function reposition() { positionMenu(); }
    document.addEventListener("pointerdown", dismiss);
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition);
    };
  }, [open]);

  useEffect(() => {
    if (open) menu.current?.querySelectorAll<HTMLElement>('[role="option"]')[activeIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [open, activeIndex]);

  function choose(version: SceneVersionSummary) {
    onChange(version.id);
    setPlacement(null);
    trigger.current?.focus();
  }

  function handleKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "Escape" || event.key === "Tab") {
      setPlacement(null);
      if (event.key === "Escape" && open) event.preventDefault();
      return;
    }
    if (["ArrowDown", "ArrowUp", "Home", "End", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      if (!open) { openMenu(); return; }
      if (event.key === "ArrowDown") setActiveIndex(index => Math.min(versions.length - 1, index + 1));
      if (event.key === "ArrowUp") setActiveIndex(index => Math.max(0, index - 1));
      if (event.key === "Home") setActiveIndex(0);
      if (event.key === "End") setActiveIndex(versions.length - 1);
      if ((event.key === "Enter" || event.key === " ") && versions[activeIndex]) choose(versions[activeIndex]);
    }
  }

  return <div className={styles.control}>
    <button ref={trigger} id={id} type="button" role="combobox" aria-expanded={open} aria-haspopup="listbox"
      aria-controls={open ? listId : undefined} aria-activedescendant={open ? `${listId}-${activeIndex}` : undefined}
      aria-describedby="configuration-explanation" disabled={disabled} className={styles.trigger}
      onKeyDown={handleKey} onClick={() => open ? setPlacement(null) : openMenu()}>
      <Layers size={17} className={styles.icon} aria-hidden="true" />
      <span className={styles.value}><strong>{selected ? configurationLabel(selected) : "Sin configuración"}</strong><small>{selected?.shop_count} {selected?.shop_count === 1 ? "zona" : "zonas"}</small></span>
      {selected?.id === versions[0]?.id && <span className={styles.badge}>Más reciente</span>}
      <ChevronDown size={16} className={open ? styles.chevronOpen : styles.chevron} aria-hidden="true" />
    </button>
    {open && createPortal(<div ref={menu} id={listId} role="listbox" aria-label="Configuraciones de escena" className={styles.menu} style={placement}>
      {versions.map((version, index) => <div key={version.id} id={`${listId}-${index}`} role="option" aria-selected={version.id === value}
        aria-label={configurationLabel(version)} className={styles.option} data-active={index === activeIndex}
        onPointerMove={() => setActiveIndex(index)} onMouseDown={event => event.preventDefault()} onClick={() => choose(version)}>
        <Layers size={17} className={styles.icon} aria-hidden="true" />
        <span className={styles.value}><strong>{configurationLabel(version)}</strong><small>{version.shop_count} {version.shop_count === 1 ? "zona de interés" : "zonas de interés"}</small></span>
        {index === 0 && <span className={styles.badge}>Más reciente</span>}
        <span className={styles.check}>{version.id === value && <Check size={17} aria-hidden="true" />}</span>
      </div>)}
    </div>, document.body)}
  </div>;
}
