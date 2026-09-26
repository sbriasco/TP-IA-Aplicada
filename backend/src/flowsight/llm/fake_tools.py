"""Herramienta ficticia de analytics para validar tool calling."""

from __future__ import annotations

from typing import Any, TypedDict

DEMO_SESSION_ID = "demo-session-001"


class SessionTrafficResult(TypedDict):
    found: bool
    session_id: str
    total_entries: int | None
    peak_hour: str | None


def get_session_traffic(session_id: str) -> SessionTrafficResult:
    """Devuelve tráfico hardcodeado; no consulta PostgreSQL ni APIs del producto."""

    if session_id == DEMO_SESSION_ID:
        return {
            "found": True,
            "session_id": DEMO_SESSION_ID,
            "total_entries": 42,
            "peak_hour": "15:00-16:00",
        }
    return {
        "found": False,
        "session_id": session_id,
        "total_entries": None,
        "peak_hour": None,
    }


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_session_traffic",
            "description": (
                "Obtiene el tráfico de una sesión analítica. "
                "Solo hay datos de muestra para demo-session-001."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Identificador de sesión",
                    }
                },
                "required": ["session_id"],
            },
        },
    }
]


def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta solo la tool ficticia registrada."""

    if name != "get_session_traffic":
        return {"error": "unknown_tool", "name": name}
    session_id = str(arguments.get("session_id", ""))
    return dict(get_session_traffic(session_id))
