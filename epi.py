#!/usr/bin/env python3
"""
EpiForecast-MX  ·  Consola Interactiva con IA (v3.0)
Instituto Mexicano del Seguro Social

CLI de operaciones para el pipeline de pronostico epidemiologico
de condiciones neurologicas y de salud mental (F32, G20, G30).

Autor: Javier Rebull · Equipo EpiForecast-MX
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import re
import readline
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

from epi_modules.engine import EpiEngine
from epi_modules.features.ai_chat import handle_chat
from epi_modules.features.dashboard import show_dashboard
from epi_modules.features.data_cache import ProjectDataCache
from epi_modules.features.data_explorer import show_data_explorer
from epi_modules.features.forecast_viewer import show_forecast_viewer
from epi_modules.features.model_browser import show_model_browser
from epi_modules.intent import (
    classify_intent,
    extract_folder_filter,
    fuzzy_suggest,
    normalize_typos,
)
from epi_modules.theme import IMSS_THEME
from epi_modules.views.approval import (
    show_approval_gate,
    show_execution_progress,
    show_result_card,
)
from epi_modules.views.banner import show_banner
from epi_modules.views.common import (
    show_history,
    show_log_viewer,
    show_pipeline_status,
    show_python_scripts,
    show_session_stats,
)
from epi_modules.views.health import show_health_dashboard
from epi_modules.views.help_menu import show_help_menu
from epi_modules.views.targets import show_targets
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.rule import Rule
from rich.status import Status
from rich.text import Text
import typer

# -- Setup global ------------------------------------------------------
console = Console(theme=IMSS_THEME)
app = typer.Typer(add_completion=False)

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "epi.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s \u2502 %(levelname)-7s \u2502 %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# -- Historial persistente ---------------------------------------------
HISTORY_FILE = Path(".epi_history.json")


def _load_history() -> list[str]:
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text())
            return data.get("history", [])[-100:]
        except Exception:
            pass
    return []


def _save_history(history: list[str]) -> None:
    import contextlib

    with contextlib.suppress(Exception):
        HISTORY_FILE.write_text(json.dumps({"history": history[-100:]}, indent=2))


# -- Prompt contextual -------------------------------------------------
def build_prompt(engine: EpiEngine, cache: ProjectDataCache) -> Text:
    """Prompt con modelo activo + stats."""
    s = engine.stats
    parts = Text()
    # Modelo activo
    modelo = cache.modelo_activo
    parts.append(f"[{modelo}] ", style="info")
    # Stats
    if s.total > 0:
        parts.append(f"{s.successes}/{s.total} ", style="verde")
    parts.append("epi", style="dorado")
    parts.append(" > ", style="verde")
    return parts


# -- REPL principal ----------------------------------------------------
@app.command()
def main() -> None:
    """EpiForecast-MX · Consola Interactiva con IA v3.0"""

    engine = EpiEngine()
    cache = ProjectDataCache()

    # Pre-flight
    errors, warnings_list = engine.check_environment()
    if errors:
        show_banner(console)
        console.print(
            Panel(
                "[guinda]ERRORES CRITICOS:\n\n"
                + "\n".join(f"  - {e}" for e in errors)
                + "\n\n[gris]Corrige estos problemas antes de continuar.[/gris][/guinda]",
                title="[error]FALLO DE INICIALIZACION[/error]",
                border_style="guinda",
                padding=(1, 2),
            )
        )
        raise typer.Exit(code=1)

    engine.parse_makefile()
    engine.history = _load_history()

    # Cargar historial en readline para flecha arriba/abajo
    for entry in engine.history:
        readline.add_history(entry)

    # Bienvenida
    show_banner(console)
    show_health_dashboard(
        console,
        errors,
        warnings_list,
        n_targets=len(engine.targets),
        has_api_key=bool(engine.api_key),
    )
    console.print(
        Align.center(
            "[sutil]Escribe [dorado]ayuda[/dorado] para ver comandos · "
            "[dorado]salir[/dorado] para cerrar[/sutil]",
        )
    )
    console.print()
    logging.info("=== Sesion de epi v3.0 iniciada ===")

    # Historial conversacional para contexto en preguntas anidadas
    chat_history: list[dict[str, str]] = []

    # REPL
    while True:
        try:
            from rich.prompt import Prompt

            user_input = Prompt.ask(build_prompt(engine, cache)).strip()
            if not user_input:
                continue

            engine.history.append(user_input)
            cmd_normalized = normalize_typos(user_input.lower().strip())
            intent = classify_intent(cmd_normalized)

            # -- Intents directos (sin ejecucion Make) --
            if intent == "saludo":
                hour = datetime.now().hour
                greeting = (
                    "Buenos dias"
                    if hour < 12
                    else "Buenas tardes"
                    if hour < 19
                    else "Buenas noches"
                )
                console.print(
                    f"\n  [verde]{greeting}[/verde] Soy [dorado]epi[/dorado], "
                    f"tu consola de operaciones."
                    f"\n  [sutil]Escribe [dorado]ayuda[/dorado] para ver que "
                    f"puedo hacer.[/sutil]\n",
                )
                continue

            if intent == "salir":
                break

            if intent == "limpiar":
                show_banner(console)
                continue

            if intent == "banner":
                show_banner(console)
                continue

            if intent == "dashboard":
                show_dashboard(console, cache)
                continue

            if intent == "chat":
                engine.model_name = handle_chat(
                    console,
                    user_input,
                    cache,
                    engine.api_key,
                    engine.model_name,
                    chat_history=chat_history,
                )
                continue

            if intent == "datos":
                args = re.sub(r"^datos?\s*", "", cmd_normalized).strip()
                show_data_explorer(console, cache, args)
                continue

            if intent == "modelos":
                args = re.sub(r"^modelos?\s*", "", cmd_normalized).strip()
                show_model_browser(console, cache, args)
                continue

            if intent == "pronostico":
                args = re.sub(r"^(pronostico|forecast)\s*", "", cmd_normalized).strip()
                show_forecast_viewer(console, cache, args)
                continue

            if intent == "scripts":
                folder = extract_folder_filter(cmd_normalized)
                show_python_scripts(console, folder)
                continue

            if intent == "ayuda":
                show_help_menu(console)
                continue

            if intent == "targets":
                show_targets(console, engine)
                continue

            if intent == "stats":
                show_session_stats(console, engine)
                continue

            if intent == "logs":
                show_log_viewer(console, LOG_FILE)
                continue

            if intent == "pipeline":
                show_pipeline_status(console, engine)
                continue

            if intent == "salud":
                errs, warns = engine.check_environment()
                show_health_dashboard(
                    console,
                    errs,
                    warns,
                    n_targets=len(engine.targets),
                    has_api_key=bool(engine.api_key),
                )
                continue

            if intent == "historial":
                show_history(console, engine)
                continue

            # -- Comando directo `make ...` --
            if cmd_normalized.startswith("make "):
                commands = [user_input]
                explanation = "Comando directo del operador."

            # -- Atajo: nombre de target sin `make` --
            elif cmd_normalized in engine.targets:
                commands = [f"make {cmd_normalized}"]
                explanation = f"Target '{cmd_normalized}' detectado directamente."

            # -- Procesamiento con IA --
            else:
                with Status(
                    "[dorado]  Buscando target...[/dorado]",
                    spinner="dots",
                    spinner_style="dorado",
                    console=console,
                ):
                    brain = engine.translate(cmd_normalized)

                if not brain.get("is_valid"):
                    err_msg = brain.get("error", "No pude interpretar esa instruccion.")
                    suggestion = brain.get("suggestion", "")

                    # Fuzzy suggest
                    all_cmds = list(engine.targets.keys()) + [
                        "ayuda",
                        "targets",
                        "dashboard",
                        "datos",
                        "modelos",
                        "pronostico",
                        "stats",
                        "pipeline",
                        "historial",
                        "pregunta",
                        "chat",
                        "salud",
                        "scripts",
                    ]
                    fuzzy = fuzzy_suggest(cmd_normalized.split()[0], all_cmds)
                    if fuzzy:
                        suggestion = f"Quisiste decir '{fuzzy}'?"

                    content = f"[guinda]{err_msg}[/guinda]"
                    if suggestion:
                        content += f"\n[info]{suggestion}[/info]"
                    console.print(
                        Panel(
                            content,
                            border_style="guinda.dim",
                            padding=(0, 2),
                        )
                    )
                    continue

                commands = brain.get("commands", [])
                explanation = brain.get("explanation", "")

            if not commands:
                console.print("[gris]  Sin comandos para ejecutar.[/gris]")
                continue

            logging.info(f"Instruccion: '{user_input}' -> {commands}")

            # Gate de aprobacion
            approved = show_approval_gate(console, engine, commands, explanation)
            if not approved:
                engine.stats.cancel()
                logging.info(f"Rechazado por operador: {commands}")
                console.print("\n  [gris]Operacion cancelada por el operador.[/gris]\n")
                continue

            # Ejecucion
            console.print()
            console.print(Rule("[verde]EJECUCION EN CURSO[/verde]", style="verde.dim"))

            for i, cmd in enumerate(commands, 1):
                show_execution_progress(console, cmd, i, len(commands))

                with Status(
                    "[verde]  Procesando...[/verde]",
                    spinner="dots2",
                    spinner_style="verde",
                    console=console,
                ):
                    returncode, stdout, stderr, duration = engine.execute_with_output(cmd)

                success = returncode == 0
                engine.stats.record(cmd, success, duration)
                logging.info(
                    f"{'OK' if success else 'FAIL'} {cmd} | "
                    f"Codigo: {returncode} | Duracion: {duration.total_seconds():.1f}s",
                )
                show_result_card(console, cmd, returncode, stdout, stderr, duration)

                if not success and i < len(commands):
                    console.print(
                        "\n  [guinda]Abortando cadena de ejecución por fallo.[/guinda]\n",
                    )
                    for _ in commands[i:]:
                        engine.stats.cancel()
                    break

            console.print(Rule(style="verde.dim"))
            console.print()

        except KeyboardInterrupt:
            console.print("\n")
            if Confirm.ask(Text("Cerrar sesión?", style="dorado"), default=False):
                break
            continue
        except EOFError:
            break
        except Exception as e:
            logging.error(f"Error inesperado: {e}")
            console.print(f"\n  [error]Error inesperado: {e}[/error]\n")

    # Cierre
    _save_history(engine.history)
    console.print()
    console.print(Rule("[dorado]FIN DE SESIÓN[/dorado]", style="dorado"))
    console.print()
    if engine.stats.total > 0:
        show_session_stats(console, engine)
    console.print(
        Align.center(
            f"[verde]Sesión cerrada · {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · "
            f"Bitácora: {LOG_FILE}[/verde]",
        )
    )
    console.print()
    logging.info("=== Sesion de epi finalizada ===")


if __name__ == "__main__":
    app()
