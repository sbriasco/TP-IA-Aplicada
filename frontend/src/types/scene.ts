/** Tope de locales por versión (`shops.maxItems` del contrato). */
export const MAX_SHOPS_PER_VERSION = 20;

export type ZoneRole = "front" | "interior" | "showcase";

export type EntryDirection = "a_to_b" | "b_to_a";

/** Coordenada normalizada `[x, y]` en [0, 1] respecto del frame de referencia. */
export type Point = [number, number];

export type Zones = Partial<Record<ZoneRole, Point[]>>;

export interface EntryLine {
  start: Point;
  end: Point;
  entry_direction: EntryDirection;
}

export interface ShopInput {
  /** Local existente de la cámara; `null` crea uno nuevo. */
  shop_id?: string | null;
  name: string;
  zones: Zones;
  entry_line: EntryLine | null;
}

export interface SceneVersionCreate {
  reference_session_id: string;
  /** Versión cargada en el editor; solo sirve para advertir `newer_version_exists`. */
  base_version_id?: string | null;
  shops: ShopInput[];
}

export interface SceneVersionSummary {
  id: string;
  camera_id: string;
  version_number: number;
  reference_session_id: string;
  frame_width: number;
  frame_height: number;
  created_by_machine_id: string | null;
  created_at: string;
  shop_count: number;
}

/** Local de una versión guardada: siempre tiene `shop_id` y línea de entrada. */
export interface SceneShop {
  shop_id: string;
  name: string;
  /** La API devuelve null para las áreas que no fueron dibujadas. */
  zones: Partial<Record<ZoneRole, Point[] | null>>;
  entry_line: EntryLine;
}

export interface SceneVersion extends SceneVersionSummary {
  shops: SceneShop[];
}

export type SceneIssueElement =
  | "version"
  | "shop"
  | "zone:front"
  | "zone:interior"
  | "zone:showcase"
  | "entry_line";

export interface SceneIssue {
  /** Código estable de la regla (ver data-model.md). */
  rule: string;
  element: SceneIssueElement;
  shop_index: number | null;
  shop_name: string | null;
  message: string;
}

export type CreateSceneVersionResult =
  | { ok: true; version: SceneVersion; warnings: SceneIssue[] }
  | { ok: false; errors: SceneIssue[] };

export interface AnalysisJob {
  id: string;
  session_id: string;
  kind: "synthetic_base_flow" | "video_analysis";
  scene_version_id: string | null;
  status: "pending" | "processing" | "completed" | "failed";
  created_at: string;
}

/** Relaciones de aspecto (ancho/alto) que informa `aspect_ratio_mismatch`. */
export interface AspectRatios {
  video: number;
  version: number;
}
