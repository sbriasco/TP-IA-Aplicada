"""Cliente mínimo y validación local contra Azure AI Foundry.

No expone chat HTTP. Las métricas del producto no se calculan aquí: el modelo
solo puede usar herramientas acotadas de analytics registradas explícitamente
(p. ej. get_session_traffic ficticia). No ejecuta SQL arbitrario generado por
el modelo. Credenciales solo vía variables de entorno / `.env` local.
"""
