export function configurationLabel(version: {
  version_number: number;
  display_name?: string | null;
}): string {
  const name = version.display_name?.trim();
  return name ? name : `Configuración ${version.version_number}`;
}
