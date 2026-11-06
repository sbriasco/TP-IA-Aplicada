import type { AreaRef } from "../api/visitPatterns";

export interface SequenceZone {
  id: string;
  name: string;
}

const ROLE_NAME: Record<AreaRef["zone_role"], string> = {
  front: "Frente",
  interior: "Interior",
  window: "Vidriera",
};

function sameArea(left: AreaRef, right: AreaRef): boolean {
  return left.shop_id === right.shop_id && left.zone_role === right.zone_role;
}

function areaLabel(area: AreaRef, zones: SequenceZone[]): string {
  const role = ROLE_NAME[area.zone_role];
  const name = zones.find((zone) => zone.id === area.shop_id)?.name.trim();
  if (name == null || name.length === 0) return role;
  const number = /(\d+)$/.exec(name);
  if (number != null) return `${role}${number[1]}`;
  return `${role} ${name}`;
}

function alternates(areas: AreaRef[]): boolean {
  if (areas.length < 2) return false;
  const start = areas[0];
  const other = areas[1];
  if (start == null || other == null || sameArea(start, other)) return false;
  return areas.every((area, index) => sameArea(area, index % 2 === 0 ? start : other));
}

export function sequenceLabel(areas: AreaRef[], zones: SequenceZone[]): string {
  if (areas.length === 0) return "";
  const labels = areas.map((area) => areaLabel(area, zones));
  if (!alternates(areas)) return labels.join(" → ");
  const outbound = Math.ceil((areas.length - 1) / 2);
  const start = labels[0] ?? "";
  const other = labels[1] ?? "";
  if (areas.length === 2) return `${start} → ${other}`;
  if (outbound <= 1) return `${start} ⇄ ${other}`;
  return `${start} ⇄ ${other} (X${outbound})`;
}
