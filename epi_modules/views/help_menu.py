"""Menu de ayuda actualizado con todas las funciones v3.0."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def show_help_menu(console: Console) -> None:
    """Menu de ayuda mejorado con todas las funciones."""
    sections = [
        (
            "COMANDOS DIRECTOS",
            [
                ("make <target>", "Ejecuta un target directamente"),
                ("<target>", "Atajo — se antepone 'make' automáticamente"),
                ("ayuda / help", "Muestra este menú"),
                ("targets", "Lista todos los targets disponibles"),
            ],
        ),
        (
            "INTELIGENCIA ARTIFICIAL",
            [
                ("pregunta <texto>", "Pregunta a la IA sobre el proyecto"),
                ("chat <texto>", "Conversación libre con IA + contexto"),
                ("<cualquier texto>?", "Pregunta detectada automáticamente"),
                ("'ejecuta las pruebas'", "--> make test (lenguaje natural)"),
            ],
        ),
        (
            "EXPLORACIÓN DE DATOS",
            [
                ("dashboard / panel", "Panel multipanel del sistema"),
                ("datos [filtro]", "Explorador del boletín epidemiológico"),
                ("modelos [filtro]", "Navegador de 333 modelos de producción"),
                ("pronostico <estado> <pad>", "Visor de pronósticos con sparklines"),
            ],
        ),
        (
            "MONITOREO",
            [
                ("stats", "Dashboard de estadísticas de sesión"),
                ("log / bitácora", "Visor de log reciente"),
                ("pipeline", "Estado del pipeline MLOps"),
                ("salud / health", "Diagnóstico del sistema"),
                ("scripts / .py", "Lista scripts Python del proyecto"),
            ],
        ),
        (
            "UTILIDADES",
            [
                ("limpia / clear", "Limpia pantalla"),
                ("banner", "Redibuja el banner"),
                ("historial", "Muestra historial de comandos"),
                ("salir / exit", "Cierra la sesión"),
            ],
        ),
    ]

    console.print()
    for title, items in sections:
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
            expand=True,
        )
        table.add_column("Comando", style="exito", min_width=30)
        table.add_column("Descripción", style="blanco")
        for cmd, desc in items:
            table.add_row(cmd, desc)
        console.print(
            Panel(
                table,
                title=f"[dorado]{title}[/dorado]",
                border_style="verde.dim",
                padding=(0, 1),
            )
        )
    console.print()
