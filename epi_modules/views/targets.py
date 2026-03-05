"""Vista agrupada de targets disponibles del Makefile."""

from rich import box
from rich.console import Console
from rich.table import Table

from ..engine import EpiEngine
from ..theme import RISK_COLORS, RISK_ICONS, RISK_LABELS

# Grupos ordenados: (titulo, lista de targets en orden deseado)
_GROUPS: list[tuple[str, list[str]]] = [
    (
        "Datos",
        ["preprocess", "reset"],
    ),
    (
        "Entrenamiento",
        [
            "train",
            "train-prophet",
            "train-deepar",
            "train-ensemble",
            "train-stacking",
            "train-all",
        ],
    ),
    (
        "SageMaker (AWS)",
        [
            "train-sagemaker",
            "train-sagemaker-build",
            "train-sagemaker-parallel",
            "train-sagemaker-fast",
            "train-sagemaker-local",
        ],
    ),
    (
        "Prediccion y reportes",
        [
            "predict",
            "predict-all",
            "tableau",
            "report",
            "bitacora",
            "compare",
            "compare-metrics",
            "tabla-produccion",
            "avance5",
            "reporte-avance5",
            "model-pipeline",
        ],
    ),
    (
        "Versionado (DVC / S3)",
        [
            "data-pull",
            "data-push",
            "data-add",
            "data-commit",
            "data-weekly",
            "data-status",
            "models-push",
            "forecast-push",
            "s3-sync",
        ],
    ),
]


def show_targets(console: Console, engine: EpiEngine) -> None:
    """Tabla rica de targets agrupados por categoria."""
    if not engine.targets:
        console.print("[gris]  No se encontraron targets en el Makefile.[/gris]")
        return

    table = Table(
        title="[dorado]DICCIONARIO DE OPERACIONES[/dorado]",
        show_header=True,
        header_style="dorado",
        border_style="verde.dim",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("", width=3, justify="center")
    table.add_column("Comando", style="exito", min_width=26)
    table.add_column("Descripcion", style="blanco")
    table.add_column("Riesgo", justify="center", width=8)

    shown: set[str] = set()
    first_group = True

    for group_title, members in _GROUPS:
        group_targets = [t for t in members if t in engine.targets]
        if not group_targets:
            continue

        if not first_group:
            table.add_row("", "", "", "")
        table.add_row(
            "",
            f"[dorado]{group_title}[/dorado]",
            "",
            "",
        )

        for name in group_targets:
            desc = engine.targets[name]
            risk = engine.assess_risk(name)
            icon = RISK_ICONS[risk]
            risk_label = f"[{RISK_COLORS[risk]}]{RISK_LABELS[risk]}[/{RISK_COLORS[risk]}]"
            table.add_row(icon, f"  make {name}", desc, risk_label)
            shown.add(name)

        first_group = False

    # Targets no categorizados (por si se agregan nuevos al Makefile)
    uncategorized = [t for t in sorted(engine.targets) if t not in shown]
    if uncategorized:
        if not first_group:
            table.add_row("", "", "", "")
        table.add_row("", "[dorado]Otros[/dorado]", "", "")
        for name in uncategorized:
            desc = engine.targets[name]
            risk = engine.assess_risk(name)
            icon = RISK_ICONS[risk]
            risk_label = f"[{RISK_COLORS[risk]}]{RISK_LABELS[risk]}[/{RISK_COLORS[risk]}]"
            table.add_row(icon, f"  make {name}", desc, risk_label)

    console.print()
    console.print(table)
    console.print(
        "[gris]  Escribe el nombre del target o descríbelo en español.[/gris]",
    )
    console.print()
