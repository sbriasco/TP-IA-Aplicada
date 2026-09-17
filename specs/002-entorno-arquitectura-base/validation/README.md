# Validación de equipos

## CPU

Ejecutar desde la raíz:

```powershell
.\scripts\verify-base.ps1 -Mode cpu
```

El informe completo queda en `.verification/` y no se versiona. `cpu-summary.json` contiene únicamente versiones, modo, resultado, medianas y limitaciones generales anonimizadas.

## PC de referencia RTX 5080

En la PC de referencia, preparar el mismo commit y entorno siguiendo el `README.md`, confirmar que PyTorch detecta CUDA y ejecutar:

```powershell
.\scripts\verify-base.ps1 -Mode gpu
```

Registrar el resultado de GPU por separado. Hasta ejecutar este procedimiento en esa PC, su estado es `not_evaluated`; la ausencia de esa medición no invalida el resultado CPU y no permite extrapolar rendimiento de video.
