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
      {zero ? (
        <p className={styles.note}>0 visitas con posible compra estimada</p>
      ) : (
        <p className={styles.value}>
          {purchases.visit_count} visitas con posible compra estimada
        </p>
      )}
      <p className={styles.note}>
        Umbral: {purchases.minimum_seconds} segundo
        {purchases.minimum_seconds === "1" ? "" : "s"} de video de solape exclusivo con una bolsa.
      </p>
      <p className={styles.disclaimer}>
        Es una estimación a partir de bolsas observadas; no es una venta confirmada.
      </p>
      {purchases.precision_uncommitted && (
        <p className={styles.disclaimer}>
          La precisión de la posible compra estimada no está comprometida.
        </p>
      )}
    </section>
  );
}
