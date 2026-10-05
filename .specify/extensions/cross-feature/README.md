# Cross-feature 1.0.0

Origen: https://github.com/polarizertech/spec-kit-extensions/tree/main/extensions/cross-feature

Instalación local realizada el 2026-10-03. El comando upstream está adaptado como
skill en `.github/skills/speckit-extn-cross-feature/SKILL.md`, siguiendo la
estructura de este repositorio. Se conservan plantilla y scripts para ambos shells.

Uso en el agente: `/speckit-extn-cross-feature` (nombre upstream:
`/speckit.extn.cross-feature`). Ejecutar después de especificar y antes de planificar.

Adaptaciones: el script PowerShell usa el resolver `Get-FeaturePathsEnv` de Spec Kit,
acepta `-Json` como switch y `-AnalysisFocus` como texto. `-CheckOnly` verifica rutas
sin crear el informe ni agregar aclaraciones a la spec. El script Bash elimina el
prefijo de rama para resolver `feature/NNN-slug` hacia `specs/NNN-slug`.

Verificación de instalación:

```powershell
.specify/scripts/powershell/cross-feature-check-all-features.ps1 -Json -CheckOnly
```

La ejecución normal crea `cross-feature-analysis.md` y agrega una aclaración a la
spec. La generación de un informe por el agente es un paso posterior; verificar
rutas no realiza el análisis. Todos los archivos de instalación están destinados
a versionarse para que se compartan entre equipos. Este instalador comunitario
no usa el registro de extensiones oficial de Spec Kit; la skill es la entrada.

Commit upstream instalado: ae3f42d582cca04f9c43455f6212010768ebd42d. Licencia MIT incluida en LICENSE.
