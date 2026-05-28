"""Chat conversacional con KnowledgeBase local + Gemini como fallback."""

import logging
import re

import google.generativeai as genai
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .data_cache import ProjectDataCache
from .knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# Cache global del KnowledgeBase (se inicializa lazy)
_kb_instance: KnowledgeBase | None = None


def _get_kb(cache: ProjectDataCache) -> KnowledgeBase:
    """Obtiene o crea la instancia singleton del KnowledgeBase."""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase(cache)
    return _kb_instance


def handle_chat(
    console: Console,
    query: str,
    cache: ProjectDataCache,
    api_key: str | None,
    model_name: str | None,
    chat_history: list[dict[str, str]] | None = None,
) -> str | None:
    """Maneja una pregunta del usuario. Retorna model_name actualizado."""
    # Limpiar prefijo
    clean = re.sub(r"^(pregunta|chat)\s+", "", query, flags=re.IGNORECASE).strip()
    if not clean:
        console.print("[gris]  Escribe tu pregunta después del comando.[/gris]")
        return model_name

    if chat_history is None:
        chat_history = []

    kb = _get_kb(cache)

    # 1) Intentar respuesta local con KnowledgeBase
    # Enriquecer pregunta con contexto del historial reciente
    enriched = _enrich_from_history(clean, chat_history)
    local = kb.answer(enriched)

    # Detectar preguntas conceptuales que se benefician de Gemini
    _conceptual_triggers = [
        "que es",
        "qué es",
        "como funciona",
        "cómo funciona",
        "explica",
        "explicame",
        "explícame",
        "describe",
        "para que sirve",
        "para qué sirve",
        "en que consiste",
        "como opera",
        "cómo opera",
        "que hace",
        "qué hace",
        "diferencia entre",
    ]
    q_lower = clean.lower()
    is_conceptual = any(t in q_lower for t in _conceptual_triggers)

    if local and not (is_conceptual and api_key):
        console.print()
        console.print(
            Panel(
                Markdown(local),
                title="[dorado]Respuesta (datos reales)[/dorado]",
                border_style="verde.dim",
                padding=(1, 2),
            )
        )
        console.print()
        chat_history.append({"role": "user", "text": clean})
        chat_history.append({"role": "assistant", "text": local})
        return model_name

    # 2) Gemini (fallback o complemento para preguntas conceptuales)
    if not api_key:
        if local:
            # Mostrar respuesta local si existe pero no hay API key para complementar
            console.print()
            console.print(
                Panel(
                    Markdown(local),
                    title="[dorado]Respuesta (datos reales)[/dorado]",
                    border_style="verde.dim",
                    padding=(1, 2),
                )
            )
            console.print()
            chat_history.append({"role": "user", "text": clean})
            chat_history.append({"role": "assistant", "text": local})
        else:
            console.print(
                "[alerta]No pude responder localmente y GEMINI_API_KEY no está "
                "configurada. Intenta reformular la pregunta o configura la API.[/alerta]",
            )
        return model_name

    # Construir contexto ultra-detallado desde KnowledgeBase
    rich_context = kb.build_rich_context(enriched)

    # Si hay respuesta local, incluirla como contexto adicional para Gemini
    local_context = ""
    if local:
        local_context = (
            f"\n\n--- Datos del proyecto (respuesta local) ---\n{local}\n"
            "Complementa esta informacion con una explicacion conceptual detallada. "
            "Incluye los datos del proyecto en tu respuesta.\n"
        )

    system_msg = (
        "Eres el asistente de inteligencia del proyecto EpiForecast-MX del IMSS.\n"
        "Tienes acceso a la base de conocimiento completa del proyecto.\n"
        "Respondes en espanol, con precision numerica y formato Markdown.\n"
        "Siempre que cites metricas, usa los valores exactos del contexto.\n"
        "Si no tienes suficiente informacion, dilo claramente.\n"
        "No inventes datos; usa solo lo que aparece en el contexto.\n\n"
        f"{rich_context}{local_context}"
    )

    # Agregar historial conversacional reciente para contexto
    history_block = _build_history_block(chat_history)
    if history_block:
        system_msg += f"\n\n--- Historial reciente ---\n{history_block}"

    try:
        from rich.status import Status

        if not model_name:
            genai.configure(api_key=api_key)
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    model_name = m.name
                    break
            if not model_name:
                model_name = "models/gemini-1.5-flash"

        with Status(
            "[dorado]  Consultando IA (con contexto completo)...[/dorado]",
            spinner="dots",
            spinner_style="dorado",
            console=console,
        ):
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                f"{system_msg}\n\nPregunta del operador: {clean}",
            )

        answer = response.text if response.text else "Sin respuesta de la IA."
        console.print()
        console.print(
            Panel(
                Markdown(answer),
                title="[dorado]Respuesta IA (contexto enriquecido)[/dorado]",
                border_style="verde.dim",
                padding=(1, 2),
            )
        )
        console.print()

        chat_history.append({"role": "user", "text": clean})
        chat_history.append({"role": "assistant", "text": answer})

    except Exception as e:
        logging.error(f"Error en chat IA: {e}")
        console.print(f"[error]Error consultando IA: {e}[/error]")
        # Fallback: si habia respuesta local disponible, mostrarla en lugar de perderla
        if local:
            console.print()
            console.print(
                Panel(
                    Markdown(local),
                    title="[dorado]Respuesta (datos reales)[/dorado]",
                    border_style="verde.dim",
                    padding=(1, 2),
                )
            )
            console.print()
            chat_history.append({"role": "user", "text": clean})
            chat_history.append({"role": "assistant", "text": local})

    return model_name


_FOLLOWUP_PREFIXES = (
    "y ",
    "y el ",
    "y la ",
    "y los ",
    "y las ",
    "y que ",
    "y como ",
    "y cuanto",
    "y en ",
    "pero ",
    "tambien ",
    "que tal ",
    "de esos",
    "de esas",
    "esos mismo",
    "el mismo",
    "la misma",
)


def _is_followup(query: str) -> bool:
    """Detecta si la pregunta es una continuacion del tema anterior."""
    q = query.lower().strip()
    # Prefijos de continuacion explicitos
    if any(q.startswith(p) for p in _FOLLOWUP_PREFIXES):
        return True
    # Preguntas muy cortas sin sujeto propio (1-2 palabras): "hombres?", "jalisco?"
    words = q.rstrip("?!. ").split()
    return len(words) <= 2


def _enrich_from_history(query: str, history: list[dict[str, str]]) -> str:
    """Enriquece una pregunta de seguimiento con contexto del historial reciente.

    Solo inyecta entidades del historial cuando la pregunta es claramente una
    continuacion del tema anterior (comienza con "y", "pero", "tambien", etc.
    o es muy corta). Preguntas con tema propio no se enriquecen.
    """
    if not history:
        return query

    if not _is_followup(query):
        return query

    from .knowledge_base import _detect_entities, _extract_weeks

    current = _detect_entities(query)
    has_pad = current.get("padecimiento") is not None
    has_est = current.get("estado") is not None
    has_week = bool(current.get("_weeks"))

    if has_pad and has_est and has_week:
        return query

    # Buscar en los ultimos 4 turnos del usuario
    recent_user = [h["text"] for h in history[-6:] if h["role"] == "user"]
    if not recent_user:
        return query

    parts: list[str] = []
    for prev_q in reversed(recent_user):
        prev_ent = _detect_entities(prev_q)
        if not has_pad and prev_ent.get("padecimiento"):
            parts.append(prev_ent["padecimiento"])
            has_pad = True
        if not has_est and prev_ent.get("estado"):
            parts.append(prev_ent["estado"])
            has_est = True
        if not has_week:
            prev_weeks = _extract_weeks(prev_q.lower())
            if prev_weeks:
                parts.append(f"semana {prev_weeks[0]}")
                has_week = True
        if parts:
            break

    # Tambien check assistant responses for week mentions (KB may have said "semana 7")
    if not has_week:
        recent_asst = [h["text"] for h in history[-6:] if h["role"] == "assistant"]
        for prev_a in reversed(recent_asst):
            prev_weeks = _extract_weeks(prev_a.lower())
            if prev_weeks:
                parts.append(f"semana {prev_weeks[0]}")
                break

    if parts:
        return f"{query} {' '.join(parts)}"

    return query


def _build_history_block(history: list[dict[str, str]], max_turns: int = 6) -> str:
    """Construye bloque de historial conversacional para el prompt de Gemini."""
    recent = history[-max_turns:]
    if not recent:
        return ""
    lines = []
    for h in recent:
        role = "Operador" if h["role"] == "user" else "Sistema"
        text = h["text"][:300]
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def invalidate_kb() -> None:
    """Invalida el cache del KnowledgeBase (llamar despues de reentrenamiento)."""
    global _kb_instance
    if _kb_instance is not None:
        _kb_instance.invalidate()
    _kb_instance = None
