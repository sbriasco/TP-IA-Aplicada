import type { PossiblePurchases } from "../api/possiblePurchases";

import styles from "./PossiblePurchasePanel.module.css";

interface PossiblePurchasePanelProps {
  purchases: PossiblePurchases;
}

export function PossiblePurchasePanel({ purchases }: PossiblePurchasePanelProps) {
  const zero = purchases.visit_count === 0;

  return (
    <section className={styles.panel} aria-label="Posible compra estimada">
      <h2>Posible compra estimada</h2>
      <p className={zero ? styles.note : styles.value}>
        {purchases.visit_count} visitas con posible compra estimada
      </p>
    </section>
  );
}
