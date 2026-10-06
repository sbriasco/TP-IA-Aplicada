import { ArrowRight, BrainCog, UploadCloud, VectorPolygon, type LucideIcon } from "lucide-react";
import { Link } from "./Link";
import styles from "./DashboardSteps.module.css";

interface Props { onUpload: () => void; configureHref?: string; resultsHref?: string; }
interface Step { number: string; title: string; description: string; Icon: LucideIcon; href?: string; onClick?: () => void; }

export function DashboardSteps({ onUpload, configureHref, resultsHref }: Props) {
  const steps: Step[] = [
    { number: "01", title: "Cargá un video", description: "De una cámara fija", Icon: UploadCloud, onClick: onUpload },
    { number: "02", title: "Configurá la escena", description: "Dibujá zonas de análisis y accesos", Icon: VectorPolygon, href: configureHref },
    { number: "03", title: "Analizá y consultá", description: "Resultados y agente de IA", Icon: BrainCog, href: resultsHref },
  ];
  return <ol className={styles.steps} aria-label="Cómo funciona FlowSight">
    {steps.map((step, index) => {
      const content = <><span className={styles.badge}>{step.number}</span><span className={styles.copy}><strong>{step.title}</strong><small>{step.description}</small></span><step.Icon className={styles.icon} size={30} aria-hidden="true" /></>;
      return <li key={step.number}>
        {step.onClick ? <button type="button" onClick={step.onClick} className={styles.card}>{content}</button> : step.href ? <Link href={step.href} className={styles.card}>{content}</Link> : <div className={styles.card}>{content}</div>}
        {index < steps.length - 1 && <ArrowRight className={styles.arrow} size={16} aria-hidden="true" />}
      </li>;
    })}
  </ol>;
}
