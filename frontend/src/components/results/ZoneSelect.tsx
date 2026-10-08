import styles from "./results.module.css";

export function ZoneSelect({
  id,
  value,
  options,
  onChange,
  disabled = false,
  className,
}: {
  id: string;
  value: string;
  options: { id: string; name: string }[];
  onChange: (id: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  return <div className={className ? `${styles.zone} ${className}` : styles.zone}>
    <label htmlFor={id}>Zona</label>
    <select id={id} value={value} disabled={disabled || options.length === 0} onChange={(event) => onChange(event.target.value)}>
      {options.length === 0 && <option value="">Sin zonas</option>}
      {options.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
    </select>
  </div>;
}
