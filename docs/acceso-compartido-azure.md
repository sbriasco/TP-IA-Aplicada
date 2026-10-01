# Acceso compartido Azure (equipo FlowSight)

Cómo configurar PostgreSQL de integración/demo y Azure AI Foundry **sin** subir secretos a Git.

## Regla de oro

| Qué | Dónde |
|---|---|
| Passwords, API keys, `.env` real | **Fuera de Git** (WhatsApp/Teams/1Password del grupo) |
| Hostnames, nombres de deployment, región, forma de la URL | Este repo (documentación) |
| Tests / CI | PostgreSQL **local** (no hace falta Azure) |

Cada integrante: `Copy-Item .env.example .env` y completa secretos en su máquina. **Nunca** hagas commit de `.env`.

---

## 1. PostgreSQL compartido (integración / demo)

**Servicio:** Azure Database for PostgreSQL – Flexible Server  
**Host (público):** `ia-aplicada-flowsight.postgres.database.azure.com`  
**Usuario:** `flowsight`  
**Database:** `postgres`  
**Password:** pedirla al compañero que administra la suscripción (canal seguro).

### En tu `.env`

```text
FLOWSIGHT_DATABASE_URL=postgresql+psycopg://flowsight:PEGAR_PASSWORD@ia-aplicada-flowsight.postgres.database.azure.com:5432/postgres?sslmode=require
```

Si la password tiene caracteres especiales (`@`, `#`, `%`, etc.), hay que URL-encodearla.

### Firewall (obligatorio por integrante)

Azure solo acepta IPs autorizadas. En el portal:

1. Recurso `ia-aplicada-flowsight` → **Networking** / reglas de firewall  
2. Agregar **tu IP pública actual** (podés verla en https://api.ipify.org)  
3. Guardar y esperar 1–2 minutos  

Sin tu IP en el firewall, la app no conecta aunque la password sea correcta.

### Migraciones

Con la URL de Azure en `.env` (o en la variable de entorno del proceso):

```powershell
Push-Location backend
.\.venv\Scripts\alembic.exe upgrade head
Pop-Location
```

Las mismas migraciones sirven para local y Azure. El esquema base ya se aplicó en la instancia compartida; si alguien crea tablas nuevas en un PR, hay que volver a correr `upgrade head` contra Azure cuando corresponda.

### ¿Cuándo usar local vs Azure?

| Situación | URL |
|---|---|
| Tests, CI, experimentás solo | Local (`127.0.0.1`, como en `.env.example`) |
| Demo / datos compartidos del grupo | Azure (URL de arriba) |

---

## 2. Azure AI Foundry (chat analítico)

La Feature #5 validó este modelo y el chat del producto (Feature #16, specs/008) ya lo consume desde el backend con herramientas acotadas de métricas.

**Datos no secretos (ya validados):**

| Variable | Valor típico |
|---|---|
| Endpoint proyecto | `https://ia-aplicada-flowsight-resource.services.ai.azure.com/api/projects/ia-aplicada-flowsight` |
| OpenAI base (opcional) | `https://ia-aplicada-flowsight-resource.openai.azure.com/openai/v1` |
| Deployment / modelo | `gpt-5-mini` |
| Región | `brazilsouth` |
| SDK | `openai==1.109.1` |

**API key:** pedirla al equipo (canal seguro). Va en `FLOWSIGHT_AZURE_AI_API_KEY` de tu `.env`.

### Ejemplo de sección Azure en `.env` (sin clave)

```text
FLOWSIGHT_AZURE_AI_ENDPOINT=https://ia-aplicada-flowsight-resource.services.ai.azure.com/api/projects/ia-aplicada-flowsight
FLOWSIGHT_AZURE_AI_API_KEY=pegar_clave_aqui
FLOWSIGHT_AZURE_AI_DEPLOYMENT=gpt-5-mini
FLOWSIGHT_AZURE_AI_MODEL=gpt-5-mini
FLOWSIGHT_AZURE_AI_REGION=brazilsouth
FLOWSIGHT_AZURE_OPENAI_ENDPOINT=https://ia-aplicada-flowsight-resource.openai.azure.com/openai/v1
```

### Probar Foundry (opcional)

```powershell
.\scripts\validate-azure-model.ps1 -Step all
```

La API y el worker **arrancan sin** estas variables. Las necesitan el script de validación y el chat real; sin una clave configurada, el chat informa que el servicio no está configurado y el resto de la app sigue disponible. Para presentar en otra PC, seguir la [guía de demo](demo-companero.md).

Evidencia del equipo: [`specs/003-validacion-modelo-azure/validation/`](../specs/003-validacion-modelo-azure/validation/).

---

## 3. Checklist rápido para un compañero nuevo

1. Clonar repo, crear `backend\.venv` (Python 3.11) e instalar deps (`README.md`).  
2. `Copy-Item .env.example .env`.  
3. Pedir por canal seguro: **password PostgreSQL** + **API key Foundry**.  
4. Completar `.env` (local y/o Azure según vayas a trabajar).  
5. Si usás Azure PG: agregar **tu IP** al firewall.  
6. `alembic upgrade head` si apuntás a una base vacía o desactualizada.  
7. Tests sin secretos Azure: `pytest -q tests/unit -k llm` desde `backend/`.

---

## 4. Qué no hacer

- No commitear `.env`, dumps ni capturas con claves.  
- No pegar passwords/API keys en issues, PR ni chats públicos del repo.  
- No abrir el firewall a `0.0.0.0/0` salvo acuerdo explícito del grupo (y por poco tiempo).  
- No asumir que CI tiene Foundry ni Azure PostgreSQL.
